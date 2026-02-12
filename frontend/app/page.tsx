
import DebateConfig from "@/components/DebateConfig"

export default function Home() {
  return (
    <div className="flex-1 space-y-4 p-8 pt-6">
      <div className="flex items-center justify-between space-y-2">
        <h2 className="text-3xl font-bold tracking-tight">Debate Configuration</h2>
      </div>
      <DebateConfig />
    </div>
  )
}
