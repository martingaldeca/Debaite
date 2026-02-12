
"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { cn } from "@/lib/utils"
import {
    LayoutDashboard,
    MessageSquareText,
    History,
    Settings,
    BrainCircuit
} from "lucide-react"

type SidebarProps = React.HTMLAttributes<HTMLDivElement>

export function Sidebar({ className }: SidebarProps) {
    const pathname = usePathname()

    const routes = [
        {
            href: "/",
            label: "Configuration",
            icon: Settings,
            active: pathname === "/",
        },
        {
            href: "/debate",
            label: "Active Debate",
            icon: MessageSquareText,
            active: pathname === "/debate",
        },
        {
            href: "/results",
            label: "Results History",
            icon: History,
            active: pathname === "/results",
        },
        {
            href: "/analytics",
            label: "Analytics",
            icon: LayoutDashboard,
            active: pathname === "/analytics",
        },
        {
            href: "/prompts",
            label: "Prompt Library",
            icon: BrainCircuit,
            active: pathname === "/prompts",
        }
    ]

    return (
        <div className={cn("pb-12 h-screen fixed left-0 top-0 z-40 bg-card border-r w-64", className)}>
            <div className="space-y-4 py-4">
                <div className="px-3 py-2">
                    <h2 className="mb-2 px-4 text-lg font-semibold tracking-tight text-white flex items-center gap-2">
                        <BrainCircuit className="h-6 w-6 text-primary" />
                        Debaite.ai
                    </h2>
                    <div className="space-y-1">
                        <h3 className="mb-2 px-4 text-xs font-semibold tracking-tight text-muted-foreground uppercase pt-4">
                            Navigation
                        </h3>
                        {routes.map((route) => (
                            <Link
                                key={route.href}
                                href={route.href}
                                className={cn(
                                    "text-sm group flex p-3 w-full justify-start font-medium cursor-pointer hover:text-white hover:bg-white/10 rounded-lg transition",
                                    route.active ? "text-white bg-white/10" : "text-muted-foreground"
                                )}
                            >
                                <div className="flex items-center flex-1">
                                    <route.icon className={cn("h-5 w-5 mr-3", route.active ? "text-primary" : "text-muted-foreground")} />
                                    {route.label}
                                </div>
                            </Link>
                        ))}
                    </div>
                </div>
            </div>
            <div className="mt-auto px-7 pb-4 absolute bottom-0">
                <p className="text-xs text-muted-foreground">Debaite Engine v0.1.0-alpha</p>
            </div>
        </div>
    )
}

export default Sidebar;
