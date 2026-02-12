
"use client"

import React, { useEffect, useState, useRef } from "react"
import { useRouter } from "next/navigation"
import { Disc, Mic, AlertTriangle, Gavel, Activity } from "lucide-react"

interface Message {
    id: string
    participant: string
    text: string
    timestamp: string
    type: "normal" | "system" | "moderator"
}

interface Participant {
    name: string
    role: string
    status: "listening" | "speaking" | "adjudicating" | "vetoed"
    avatar?: string
    strikes: number
    confidence: number
}

interface DebateEvent {
    type: string
    participants?: { name: string; role: string; confidence_score: number }[]
    moderator?: { name: string }
    participant?: string
    text?: string
    action?: boolean
    round?: number
    strikes?: number
}

export default function DebatePage() {
    const router = useRouter()
    const [messages, setMessages] = useState<Message[]>([])
    const [participants, setParticipants] = useState<Participant[]>([])
    const [round, setRound] = useState(0)
    const [topic, setTopic] = useState("")

    const bottomRef = useRef<HTMLDivElement>(null)

    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: "smooth" })
    }, [messages])

    useEffect(() => {
        const runDebateLoop = async () => {
            const configStr = localStorage.getItem("debate_config")
            if (!configStr) {
                router.push("/")
                return
            }
            const config = JSON.parse(configStr)
            setTopic(config.topic_name)

            let debateId = ""
            try {
                // 1. Initialize Debate
                const initRes = await fetch('http://localhost:8000/debates/init', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(config)
                })
                if (!initRes.ok) throw new Error("Failed to init debate")
                const initData = await initRes.json()
                debateId = initData.debate_id
                console.log("Debate initialized:", debateId)

                // 2. Loop through steps
                let finished = false
                while (!finished) {
                    const stepRes = await fetch(`http://localhost:8000/debates/${debateId}/next`, {
                        method: 'POST'
                    })

                    if (!stepRes.ok) {
                        console.error("Step failed")
                        break
                    }

                    const stepData = await stepRes.json()
                    if (stepData.event) {
                        console.log("Event:", stepData.event)
                        handleEvent(stepData.event)
                    }

                    if (stepData.finished) {
                        finished = true
                        console.log("Debate finished")
                    }
                }

            } catch (e) {
                console.error("Debate loop error:", e)
            }
        }

        runDebateLoop()
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [])

    const handleEvent = (event: DebateEvent) => {
        if (event.type === "initial_state") {
            const parts: Participant[] = (event.participants || []).map((p) => ({
                name: p.name,
                role: p.role,
                status: "listening",
                strikes: 0,
                confidence: p.confidence_score * 100
            }))
            if (event.moderator) {
                parts.push({
                    name: event.moderator.name,
                    role: "Moderator",
                    status: "adjudicating",
                    strikes: 0,
                    confidence: 100
                })
            }
            setParticipants(parts)
        } else if (event.type === "intervention") {
            setParticipants(prev => {
                return prev
            })

            setMessages(prev => {
                // Check if moderator from message content or participant name matching moderator role
                // We need access to participants state, but it might be stale in closure unless we use functional update or ref.
                // Simplification: assume role "Moderator" is unique.

                return [...prev, {
                    id: Math.random().toString(),
                    participant: event.participant || "Unknown",
                    text: event.text || "",
                    timestamp: new Date().toLocaleTimeString(),
                    type: event.participant === "System" ? "system" : (event.action ? "moderator" : "normal")
                }]
            })

            setParticipants(prev => prev.map(p => ({
                ...p,
                status: p.name === event.participant ? "speaking" : (p.role === "Moderator" ? "adjudicating" : "listening")
            })))

            setTimeout(() => {
                setParticipants(prev => prev.map(p => ({
                    ...p,
                    status: p.role === "Moderator" ? "adjudicating" : "listening"
                })))
            }, 3000)

        } else if (event.type === "round_start") {
            setRound(event.round || 0)
        } else if (event.type === "sanction") {
            setParticipants(prev => prev.map(p =>
                p.name === event.participant ? { ...p, strikes: event.strikes || 0 } : p
            ))
        } else if (event.type === "veto") {
            setParticipants(prev => prev.map(p =>
                p.name === event.participant ? { ...p, status: "vetoed" } : p
            ))
        }
    }

    return (
        <div className="flex h-screen bg-[#0a0e17] overflow-hidden">
            <div className="flex-1 p-6 flex flex-col gap-6">
                <div className="flex justify-between items-center">
                    <div>
                        <h1 className="text-xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-purple-400">
                            Live Debate Session
                        </h1>
                        <p className="text-sm text-muted-foreground">{topic}</p>
                    </div>
                    <div className="flex items-center gap-4">
                        <div className="bg-card/50 px-4 py-2 rounded-lg border border-white/5 flex items-center gap-2">
                            <Activity className="w-4 h-4 text-green-400" />
                            <span className="text-sm font-mono">Round {round}</span>
                        </div>
                        <div className="bg-card/50 px-4 py-2 rounded-lg border border-white/5 font-mono text-sm">
                            00:42:15
                        </div>
                    </div>
                </div>

                <div className="grid grid-cols-2 gap-4 flex-1">
                    {participants.filter(p => p.role !== "Moderator").map((p, i) => (
                        <div key={p.name} className={`relative rounded-2xl overflow-hidden border ${p.status === "speaking" ? "border-blue-500 shadow-[0_0_30px_rgba(59,130,246,0.2)]" : "border-white/5"} bg-card/30 transition-all duration-500`}>
                            <div className={`absolute inset-0 bg-gradient-to-br ${i === 0 ? "from-blue-900/40" : i === 1 ? "from-purple-900/40" : "from-emerald-900/40"} to-black/80`} />

                            <div className="absolute top-4 left-4">
                                {p.status === "speaking" && (
                                    <span className="flex items-center gap-1 bg-blue-600/90 text-white text-[10px] uppercase font-bold px-2 py-1 rounded">
                                        <Mic className="w-3 h-3" /> Speaking
                                    </span>
                                )}
                                {p.status === "vetoed" && (
                                    <span className="flex items-center gap-1 bg-red-600/90 text-white text-[10px] uppercase font-bold px-2 py-1 rounded">
                                        <AlertTriangle className="w-3 h-3" /> Vetoed
                                    </span>
                                )}
                                {p.status === "listening" && (
                                    <span className="flex items-center gap-1 bg-black/50 text-muted-foreground text-[10px] uppercase font-bold px-2 py-1 rounded">
                                        <Disc className="w-3 h-3 animate-spin" /> Listening
                                    </span>
                                )}
                                {p.strikes > 0 && (
                                    <div className="mt-2 flex gap-1">
                                        {Array(p.strikes).fill(0).map((_, i) => (
                                            <div key={i} className="bg-yellow-500 w-1.5 h-1.5 rounded-full" />
                                        ))}
                                    </div>
                                )}
                            </div>

                            <div className="absolute top-4 right-4 bg-black/60 backdrop-blur px-2 py-1 rounded border border-white/10">
                                <span className="text-xs font-mono text-white/80">CONF {Math.round(p.confidence)}%</span>
                            </div>

                            <div className="absolute bottom-0 left-0 right-0 p-6 bg-gradient-to-t from-black via-black/80 to-transparent">
                                <h3 className="text-lg font-bold text-white">{p.name}</h3>
                                <p className="text-xs text-blue-200/80 uppercase tracking-widest">{p.role}</p>
                            </div>
                        </div>
                    ))}
                </div>

                {participants.find(p => p.role === "Moderator") && (
                    <div className="h-32 rounded-2xl border border-blue-500/30 bg-blue-950/20 relative overflow-hidden flex items-center px-8">
                        <div className="absolute inset-0 bg-[url('/grid.svg')] opacity-20" />
                        <div className="w-16 h-16 rounded-full bg-blue-600/20 flex items-center justify-center border border-blue-500/50 mr-6">
                            <Gavel className="w-8 h-8 text-blue-400" />
                        </div>
                        <div>
                            <h3 className="text-lg font-bold text-blue-100">Moderator System</h3>
                            <p className="text-sm text-blue-300/60">System Core v3.0 // Active Surveillance</p>
                        </div>
                    </div>
                )}
            </div>

            <div className="w-[400px] border-l border-white/5 flex flex-col bg-card/20">
                <div className="p-4 border-b border-white/5 font-semibold flex justify-between items-center text-sm">
                    <span>LIVE TRANSCRIPT</span>
                    <Disc className="w-4 h-4 text-green-500 animate-pulse" />
                </div>

                <div className="flex-1 overflow-y-auto p-4 space-y-6 scrollbar-thin scrollbar-thumb-white/10">
                    {messages.length === 0 && (
                        <div className="text-center text-muted-foreground py-10 text-sm">Waiting for debate start...</div>
                    )}
                    {messages.map((msg) => (
                        <div key={msg.id} className={`space-y-1 animate-in fade-in slide-in-from-bottom-2 duration-300 ${msg.type === "moderator" ? "pl-4 border-l-2 border-blue-500" : msg.type === "system" ? "opacity-50 text-xs text-center font-mono" : ""}`}>
                            {msg.type !== "system" && (
                                <div className="flex items-baseline justify-between">
                                    <span className={`text-xs font-bold ${msg.type === "moderator" ? "text-blue-400" : "text-amber-400"}`}>
                                        {msg.participant}
                                    </span>
                                    <span className="text-[10px] text-muted-foreground">{msg.timestamp}</span>
                                </div>
                            )}
                            <p className={`text-sm leading-relaxed ${msg.type === "system" ? "text-muted-foreground" : "text-gray-300"}`}>
                                {msg.text}
                                {/* Highlight type writer effect? No easy way purely via React without extra state. */}
                            </p>
                        </div>
                    ))}
                    <div ref={bottomRef} />
                </div>
            </div>
        </div>
    )
}
