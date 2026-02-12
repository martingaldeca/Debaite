
"use client"

import * as React from "react"
import { useRouter } from "next/navigation"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Check, ShieldCheck, ShieldAlert, Play, Settings2, Plus, Trash2, Users, AlertTriangle, Zap } from "lucide-react"

// --- TYPES ---
interface ProviderConfig {
    name: string
    key: string
    model: string
    status: "verified" | "unchecked" | "failed"
    defaultModel: string
    color: string
}

interface ParticipantConfig {
    id: string
    name: string
    role: string
    brain: string
    attitude_type: string
    original_position: string
}

const DEFAULT_PROVIDERS: Record<string, ProviderConfig> = {
    gemini: { name: "Gemini", key: "", model: "gemini-1.5-pro", status: "unchecked", defaultModel: "gemini-1.5-pro", color: "bg-blue-500" },
    openai: { name: "OpenAI", key: "", model: "gpt-4o", status: "unchecked", defaultModel: "gpt-4o", color: "bg-green-500" },
    claude: { name: "Anthropic", key: "", model: "claude-3-5-sonnet-latest", status: "unchecked", defaultModel: "claude-3-5-sonnet-latest", color: "bg-orange-500" },
    deepseek: { name: "DeepSeek", key: "", model: "deepseek-chat", status: "unchecked", defaultModel: "deepseek-chat", color: "bg-purple-500" },
}

export default function DebateConfig() {
    const router = useRouter()

    // --- STATE ---
    const [topic, setTopic] = React.useState("The Ship of Theseus: Identity over Time")
    const [description, setDescription] = React.useState("The Ship of Theseus is a thought experiment that raises the question of whether an object that has had all of its components replaced remains fundamentally the same object.")
    const [stances, setStances] = React.useState<string[]>([
        "Identity is based on spatio-temporal continuity.",
        "Identity is lost when composition changes entirely."
    ])

    const [providers, setProviders] = React.useState(DEFAULT_PROVIDERS)
    const [activeTab, setActiveTab] = React.useState<"brains" | "settings" | "participants">("brains")

    // Engagement Rules
    const [maxLetters, setMaxLetters] = React.useState(1000)
    const [allowInsults, setAllowInsults] = React.useState(false)
    const [allowLies, setAllowLies] = React.useState(false)
    const [moderatorEnabled, setModeratorEnabled] = React.useState(true)

    // Manual Participants
    const [participants, setParticipants] = React.useState<ParticipantConfig[]>([])

    const [isLoading, setIsLoading] = React.useState(false)

    // --- HANDLERS ---
    const addStance = () => setStances([...stances, ""])
    const removeStance = (index: number) => setStances(stances.filter((_, i) => i !== index))
    const updateStance = (index: number, val: string) => {
        const next = [...stances]
        next[index] = val
        setStances(next)
    }

    const updateProvider = (slug: string, field: keyof ProviderConfig, val: string) => {
        setProviders(prev => ({
            ...prev,
            [slug]: { ...prev[slug], [field]: val, status: field === "key" || field === "model" ? "unchecked" : prev[slug].status }
        }))
    }

    const checkStatus = async (slug: string) => {
        const p = providers[slug]
        if (!p.key) return

        // Optimistic UI update could go here

        try {
            const res = await fetch("http://localhost:8000/providers/check_status", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    provider: slug,
                    api_key: p.key,
                    model: p.model
                })
            })
            const data = await res.json()
            setProviders(prev => ({
                ...prev,
                [slug]: { ...p, status: data.status === "verified" ? "verified" : "failed" }
            }))
        } catch {
            setProviders(prev => ({ ...prev, [slug]: { ...p, status: "failed" } }))
        }
    }

    const addParticipant = () => {
        setParticipants([...participants, {
            id: Math.random().toString(),
            name: "New Debater",
            role: "scholar",
            brain: "gemini",
            attitude_type: "calm",
            original_position: stances[0] || ""
        }])
    }

    const updateParticipant = (index: number, field: keyof ParticipantConfig, val: string) => {
        const next = [...participants]
        next[index] = { ...next[index], [field]: val }
        setParticipants(next)
    }

    const removeParticipant = (index: number) => {
        setParticipants(participants.filter((_, i) => i !== index))
    }

    const handleStartDebate = () => {
        setIsLoading(true)
        try {
            const providerConfigMap: Record<string, { api_key: string, model: string }> = {}
            Object.entries(providers).forEach(([k, v]) => {
                if (v.key) {
                    providerConfigMap[k] = { api_key: v.key, model: v.model }
                }
            })

            const engagementRules = {
                max_letters: Number(maxLetters),
                insults_allowed: allowInsults,
                lies_allowed: allowLies,
            }

            // If explicit participants are added, map them. Otherwise let backend generate.
            let participantOverrides = undefined
            if (participants.length > 0) {
                participantOverrides = participants.map(p => ({
                    name: p.name,
                    role: p.role,
                    brain: p.brain, // Enum matching
                    attitude_type: p.attitude_type,
                    original_position: p.original_position
                }))
            }

            const config = {
                topic_name: topic,
                description: description,
                allowed_positions: stances.filter(s => s.trim() !== ""),
                overrides: {
                    provider_config: providerConfigMap,
                    ...engagementRules,
                    participants: participantOverrides,
                    // Moderator override if disabled or enabled differently
                    moderator: moderatorEnabled ? { role: "Judge" } : undefined
                }
                // If moderator disabled, we should probably set it to null, but backend expects dict for override.
                // If override is present, it uses it. If not present, it uses legacy check.
                // We'll trust backend handles empty/null if we pass explicit "moderator": None equivalent?
                // Actually base.py checks `overrides.get("moderator")`. If undefined loop continues.
                // To DISABLE it we might need a flag.
                // Let's assume if enabled we pass a basic config, if disabled we rely on chaos or need a specific "no_moderator" flag.
                // For now, let's just pass overrides.
            }

            localStorage.setItem("debate_config", JSON.stringify(config))
            router.push("/debate")
        } catch (e) {
            console.error(e)
            setIsLoading(false)
        }
    }

    // --- RENDERERS ---

    const renderProviderRow = (slug: string, p: ProviderConfig) => (
        <div key={slug} className="p-4 rounded-lg bg-black/20 border border-white/5 space-y-3">
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <div className={`w-2 h-2 rounded-full ${p.color}`} />
                    <span className="font-bold text-sm text-gray-300">{p.name}</span>
                </div>
                {p.status === "verified" && <span className="text-[10px] bg-green-500/20 text-green-400 px-2 py-0.5 rounded-full flex items-center gap-1 border border-green-500/20"><ShieldCheck className="w-3 h-3" /> Verified</span>}
                {p.status === "failed" && <span className="text-[10px] bg-red-500/20 text-red-400 px-2 py-0.5 rounded-full flex items-center gap-1 border border-red-500/20"><ShieldAlert className="w-3 h-3" /> Failed</span>}
                {p.status === "unchecked" && <span className="text-[10px] bg-yellow-500/20 text-yellow-400 px-2 py-0.5 rounded-full flex items-center gap-1 border border-yellow-500/20"><AlertTriangle className="w-3 h-3" /> Check Needed</span>}
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                <div className="relative">
                    <Input
                        type="password"
                        placeholder="API Key"
                        value={p.key}
                        onChange={e => updateProvider(slug, "key", e.target.value)}
                        className="bg-black/40 border-white/10 text-xs h-8 font-mono"
                    />
                </div>
                <div className="flex gap-2">
                    <Input
                        placeholder="Model"
                        value={p.model}
                        onChange={e => updateProvider(slug, "model", e.target.value)}
                        className="bg-black/40 border-white/10 text-xs h-8 font-mono flex-1"
                    />
                    <Button variant="outline" size="sm" onClick={() => checkStatus(slug)} className="h-8 px-3 text-xs border-white/10 hover:bg-white/5">
                        <Check className="w-3 h-3" />
                    </Button>
                </div>
            </div>
        </div>
    )

    return (
        <div className="pb-20 px-8 max-w-6xl mx-auto space-y-8 animate-in fade-in duration-500">
            {/* Top Bar */}
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-purple-400">Configuration</h2>
                    <p className="text-xs text-muted-foreground">Customize the simulation parameters</p>
                </div>
                <div className="flex items-center gap-3">
                    <div className="flex bg-black/30 p-1 rounded-lg border border-white/5">
                        <button onClick={() => setActiveTab("brains")} className={`px-4 py-1.5 text-xs font-medium rounded-md transition-all ${activeTab === "brains" ? "bg-white/10 text-white shadow" : "text-muted-foreground hover:text-white"}`}>Brains</button>
                        <button onClick={() => setActiveTab("settings")} className={`px-4 py-1.5 text-xs font-medium rounded-md transition-all ${activeTab === "settings" ? "bg-white/10 text-white shadow" : "text-muted-foreground hover:text-white"}`}>Topic & Rules</button>
                        <button onClick={() => setActiveTab("participants")} className={`px-4 py-1.5 text-xs font-medium rounded-md transition-all ${activeTab === "participants" ? "bg-white/10 text-white shadow" : "text-muted-foreground hover:text-white"}`}>Participants</button>
                    </div>
                    <Button onClick={handleStartDebate} disabled={isLoading} className="bg-blue-600 hover:bg-blue-500 shadow-lg shadow-blue-500/20">
                        {isLoading ? "Initializing..." : <><Play className="mr-2 h-4 w-4" /> Start Simulation</>}
                    </Button>
                </div>
            </div>

            {/* TAB CONTENT: BRAINS */}
            {activeTab === "brains" && (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-2 gap-4">
                    {Object.entries(providers).map(([slug, p]) => renderProviderRow(slug, p))}
                </div>
            )}

            {/* TAB CONTENT: SETTINGS */}
            {activeTab === "settings" && (
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                    <Card className="md:col-span-2 bg-card/30 backdrop-blur border-white/5">
                        <CardHeader>
                            <CardTitle className="text-sm font-medium flex items-center gap-2"><Settings2 className="w-4 h-4 text-purple-400" /> Topic Configuration</CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            <div className="space-y-2">
                                <Label className="text-xs uppercase text-muted-foreground">Topic Title</Label>
                                <Input value={topic} onChange={e => setTopic(e.target.value)} className="bg-black/20 border-white/10 font-medium" />
                            </div>
                            <div className="space-y-2">
                                <Label className="text-xs uppercase text-muted-foreground">Description</Label>
                                <textarea
                                    value={description}
                                    onChange={e => setDescription(e.target.value)}
                                    className="w-full min-h-[100px] bg-black/20 border border-white/10 rounded-md p-3 text-sm focus:outline-none focus:ring-1 focus:ring-purple-500/50"
                                />
                            </div>
                            <div className="space-y-2">
                                <div className="flex justify-between items-center">
                                    <Label className="text-xs uppercase text-muted-foreground">Positions / Stances</Label>
                                    <Button size="sm" variant="ghost" onClick={addStance} className="h-6 text-xs text-purple-400 hover:bg-purple-500/10"><Plus className="w-3 h-3 mr-1" /> Add</Button>
                                </div>
                                <div className="space-y-2">
                                    {stances.map((s, i) => (
                                        <div key={i} className="flex gap-2">
                                            <Input value={s} onChange={e => updateStance(i, e.target.value)} className="bg-black/20 border-white/10 text-sm h-9" />
                                            <Button variant="ghost" size="sm" onClick={() => removeStance(i)} className="h-9 w-9 text-red-400 hover:bg-red-500/10"><Trash2 className="w-4 h-4" /></Button>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        </CardContent>
                    </Card>

                    <Card className="bg-card/30 backdrop-blur border-white/5">
                        <CardHeader>
                            <CardTitle className="text-sm font-medium flex items-center gap-2"><Zap className="w-4 h-4 text-yellow-400" /> Rules</CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-6">
                            <div className="space-y-4">
                                <div>
                                    <Label className="text-xs uppercase text-muted-foreground mb-1.5 block">Max Letters / Turn</Label>
                                    <Input type="number" value={maxLetters} onChange={e => setMaxLetters(Number(e.target.value))} className="bg-black/20 border-white/10" />
                                </div>
                                <div className="flex items-center justify-between p-3 bg-black/20 rounded-lg border border-white/5">
                                    <Label className="text-sm">Allow Insults</Label>
                                    <input type="checkbox" checked={allowInsults} onChange={e => setAllowInsults(e.target.checked)} className="accent-purple-500 h-4 w-4" />
                                </div>
                                <div className="flex items-center justify-between p-3 bg-black/20 rounded-lg border border-white/5">
                                    <Label className="text-sm">Allow Lies</Label>
                                    <input type="checkbox" checked={allowLies} onChange={e => setAllowLies(e.target.checked)} className="accent-red-500 h-4 w-4" />
                                </div>
                                <div className="flex items-center justify-between p-3 bg-black/20 rounded-lg border border-white/5">
                                    <Label className="text-sm">Enable Moderator</Label>
                                    <input type="checkbox" checked={moderatorEnabled} onChange={e => setModeratorEnabled(e.target.checked)} className="accent-blue-500 h-4 w-4" />
                                </div>
                            </div>
                        </CardContent>
                    </Card>
                </div>
            )}

            {/* TAB CONTENT: PARTICIPANTS */}
            {activeTab === "participants" && (
                <Card className="bg-card/30 backdrop-blur border-white/5">
                    <CardHeader className="flex flex-row items-center justify-between">
                        <CardTitle className="text-sm font-medium flex items-center gap-2"><Users className="w-4 h-4 text-blue-400" /> Manual Roster</CardTitle>
                        <Button size="sm" onClick={addParticipant} className="bg-white/10 hover:bg-white/20 text-xs"><Plus className="w-3 h-3 mr-1" /> Add Participant</Button>
                    </CardHeader>
                    <CardContent>
                        {participants.length === 0 ? (
                            <div className="text-center py-10 text-muted-foreground text-sm border-2 border-dashed border-white/10 rounded-lg">
                                No manual participants configured.<br />The system will generate random personas for each position.
                            </div>
                        ) : (
                            <div className="grid gap-3">
                                {participants.map((p, i) => (
                                    <div key={p.id} className="grid grid-cols-1 md:grid-cols-6 gap-3 p-3 bg-black/20 rounded-lg border border-white/5 items-center">
                                        <Input value={p.name} onChange={e => updateParticipant(i, "name", e.target.value)} placeholder="Name" className="bg-black/40 border-white/10 h-8 text-sm" />
                                        <select value={p.original_position} onChange={e => updateParticipant(i, "original_position", e.target.value)} className="bg-black/40 border border-white/10 h-8 text-sm rounded-md px-2 w-full truncate">
                                            <option value="" disabled>Select Stance</option>
                                            {stances.filter(s => s.trim()).map((s, idx) => (
                                                <option key={idx} value={s}>{s.length > 20 ? s.substring(0, 20) + "..." : s}</option>
                                            ))}
                                        </select>
                                        <select value={p.role} onChange={e => updateParticipant(i, "role", e.target.value)} className="bg-black/40 border border-white/10 h-8 text-sm rounded-md px-2">
                                            <option value="scholar">Scholar</option>
                                            <option value="illiterate">Illiterate</option>
                                            <option value="general_knowledge">General Knowledge</option>
                                            <option value="expert">Expert</option>
                                        </select>
                                        <select value={p.brain} onChange={e => updateParticipant(i, "brain", e.target.value)} className="bg-black/40 border border-white/10 h-8 text-sm rounded-md px-2">
                                            <option value="gemini">Gemini</option>
                                            <option value="openai">OpenAI</option>
                                            <option value="claude">Anthropic (Claude)</option>
                                            <option value="deepseek">DeepSeek</option>
                                        </select>
                                        <select value={p.attitude_type} onChange={e => updateParticipant(i, "attitude_type", e.target.value)} className="bg-black/40 border border-white/10 h-8 text-sm rounded-md px-2">
                                            <option value="calm">Calm</option>
                                            <option value="strict">Strict</option>
                                            <option value="fair">Fair</option>
                                            <option value="aggressive">Aggressive</option>
                                            <option value="passive">Passive</option>
                                            <option value="sarcastic">Sarcastic</option>
                                        </select>
                                        <div className="flex justify-end">
                                            <Button variant="ghost" size="sm" onClick={() => removeParticipant(i)} className="h-8 w-8 text-red-400 hover:bg-red-500/10"><Trash2 className="w-4 h-4" /></Button>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}
                    </CardContent>
                </Card>
            )}

            <div className="text-center text-[10px] text-white/20 pt-10">
                Debaite Engine v3.1.0 • Built with Next.js & FastAPI • Stitch Design System
            </div>
        </div>
    )
}
