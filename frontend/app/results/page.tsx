
"use client"

import React, { useEffect, useState } from "react"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts"
import { Trophy, Clock, DollarSign, Activity, FileText } from "lucide-react"

interface DebateResult {
    id: string
    date: string
    topic: string
    winner?: string
    metadata?: {
        topic?: string
        description?: string
        total_rounds_configured?: number
        total_estimated_cost_usd?: number
        id?: string
    }
    evaluation?: {
        global_outcome?: {
            winner_name?: string
            average_scores?: Record<string, number>
            vote_distribution?: Record<string, number>
            best_intervention?: {
                text?: string
                participant?: string
            }
        }
    }
}

export default function ResultsPage() {
    const [results, setResults] = useState<DebateResult[]>([])
    const [selectedResult, setSelectedResult] = useState<DebateResult | null>(null)

    useEffect(() => {
        fetch('http://localhost:8000/results')
            .then(res => res.json())
            .then((data: DebateResult[]) => setResults(data))
            .catch(err => console.error(err))
    }, [])

    const handleSelect = (id: string) => {
        fetch(`http://localhost:8000/results/${id}`)
            .then(res => res.json())
            .then((data: DebateResult) => setSelectedResult(data))
            .catch(err => console.error(err))
    }

    return (
        <div className="p-8 space-y-6">
            <h1 className="text-3xl font-bold tracking-tight">Debate Results History</h1>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 h-[80vh]">
                {/* List */}
                <Card className="col-span-1 border-r border-border overflow-auto">
                    <CardHeader>
                        <CardTitle>Past Debates</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-2">
                        {results.map((r) => (
                            <div
                                key={r.id}
                                onClick={() => handleSelect(r.id)}
                                className={`p-3 rounded-lg border cursor-pointer hover:bg-muted/50 transition-colors text-foreground ${selectedResult?.metadata?.id === r.id ? "bg-muted border-primary/50" : "border-transparent"}`}
                            >
                                <div className="flex justify-between items-start mb-1">
                                    <span className="font-semibold text-sm line-clamp-1">{r.topic}</span>
                                    <span className="text-[10px] text-muted-foreground whitespace-nowrap">{new Date(r.date).toLocaleDateString()}</span>
                                </div>
                                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                                    <Trophy className="w-3 h-3 text-yellow-500" />
                                    Winner: {r.winner || "None"}
                                </div>
                            </div>
                        ))}
                    </CardContent>
                </Card>

                {/* Details */}
                <div className="col-span-2 space-y-6 overflow-auto pr-2">
                    {selectedResult ? (
                        <>
                            <Card>
                                <CardHeader className="flex flex-row items-center justify-between">
                                    <div>
                                        <CardTitle className="text-xl text-primary">{selectedResult.metadata?.topic}</CardTitle>
                                        <p className="text-sm text-muted-foreground mt-1">{selectedResult.metadata?.description}</p>
                                    </div>
                                    <div className="bg-green-500/10 text-green-400 px-3 py-1 rounded-full text-xs font-mono border border-green-500/20">
                                        Completed
                                    </div>
                                </CardHeader>
                                <CardContent className="grid grid-cols-4 gap-4 mt-4">
                                    <div className="p-4 bg-card/50 rounded-lg border border-border flex flex-col items-center justify-center text-center">
                                        <Trophy className="w-8 h-8 text-yellow-500 mb-2" />
                                        <div className="text-2xl font-bold">{selectedResult.evaluation?.global_outcome?.winner_name || "Tie"}</div>
                                        <div className="text-xs text-muted-foreground uppercase">Winner</div>
                                    </div>
                                    <div className="p-4 bg-card/50 rounded-lg border border-border flex flex-col items-center justify-center text-center">
                                        <Clock className="w-8 h-8 text-blue-500 mb-2" />
                                        <div className="text-2xl font-bold">{selectedResult.metadata?.total_rounds_configured}</div>
                                        <div className="text-xs text-muted-foreground uppercase">Rounds</div>
                                    </div>
                                    <div className="p-4 bg-card/50 rounded-lg border border-border flex flex-col items-center justify-center text-center">
                                        <DollarSign className="w-8 h-8 text-green-500 mb-2" />
                                        <div className="text-2xl font-bold">${selectedResult.metadata?.total_estimated_cost_usd?.toFixed(4)}</div>
                                        <div className="text-xs text-muted-foreground uppercase">Total Cost</div>
                                    </div>
                                    <div className="p-4 bg-card/50 rounded-lg border border-border flex flex-col items-center justify-center text-center">
                                        <Activity className="w-8 h-8 text-purple-500 mb-2" />
                                        <div className="text-2xl font-bold">9.4</div>
                                        <div className="text-xs text-muted-foreground uppercase">Reasoning Score</div>
                                    </div>
                                </CardContent>
                            </Card>

                            <div className="grid grid-cols-2 gap-6">
                                <Card>
                                    <CardHeader><CardTitle>Participant Scores</CardTitle></CardHeader>
                                    <CardContent className="h-[200px]">
                                        <ResponsiveContainer width="100%" height="100%">
                                            <BarChart data={Object.entries(selectedResult.evaluation?.global_outcome?.average_scores || {}).map(([k, v]) => ({ name: k, score: v }))}>
                                                <XAxis dataKey="name" fontSize={10} />
                                                <YAxis />
                                                <Tooltip cursor={{ fill: 'transparent' }} contentStyle={{ backgroundColor: '#1a1a1a', border: '1px solid #333' }} />
                                                <Bar dataKey="score" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                                            </BarChart>
                                        </ResponsiveContainer>
                                    </CardContent>
                                </Card>
                                <Card>
                                    <CardHeader><CardTitle>Vote Distribution</CardTitle></CardHeader>
                                    <CardContent className="h-[200px]">
                                        <ResponsiveContainer width="100%" height="100%">
                                            <BarChart data={Object.entries(selectedResult.evaluation?.global_outcome?.vote_distribution || {}).map(([k, v]) => ({ name: k, votes: v }))}>
                                                <XAxis dataKey="name" fontSize={10} />
                                                <YAxis allowDecimals={false} />
                                                <Tooltip cursor={{ fill: 'transparent' }} contentStyle={{ backgroundColor: '#1a1a1a', border: '1px solid #333' }} />
                                                <Bar dataKey="votes" fill="#8b5cf6" radius={[4, 4, 0, 0]} />
                                            </BarChart>
                                        </ResponsiveContainer>
                                    </CardContent>
                                </Card>
                            </div>

                            <Card>
                                <CardHeader><CardTitle>Transcript Highlight</CardTitle></CardHeader>
                                <CardContent>
                                    <div className="p-4 rounded bg-muted/30 border border-muted italic text-sm text-gray-400">
                                        &quot;{selectedResult.evaluation?.global_outcome?.best_intervention?.text || "No highlights available."}&quot;
                                        <div className="mt-2 text-right text-xs font-bold not-italic text-primary">— {selectedResult.evaluation?.global_outcome?.best_intervention?.participant}</div>
                                    </div>
                                </CardContent>
                            </Card>
                        </>
                    ) : (
                        <div className="flex items-center justify-center h-full text-muted-foreground">
                            <div className="text-center">
                                <FileText className="w-12 h-12 mx-auto mb-4 opacity-50" />
                                <p>Select a debate to view results</p>
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    )
}
