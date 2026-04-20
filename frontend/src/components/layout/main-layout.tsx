import { NavLink, Outlet } from "react-router-dom";
import { Activity, GitPullRequest, Network, Shield } from "lucide-react";

import { cn } from "@/lib/utils";
import { ThemeToggle } from "@/components/layout/theme-toggle";

const navItems = [
  { to: "/", label: "Overview", icon: Activity, end: true },
  { to: "/lineage", label: "Lineage", icon: Network },
  { to: "/governance", label: "Governance", icon: Shield },
];

export function MainLayout() {
  return (
    <div className="flex min-h-screen flex-col bg-background text-foreground">
      <header className="sticky top-0 z-40 border-b border-border/60 bg-background/80 backdrop-blur-md">
        <div className="mx-auto flex h-14 max-w-7xl items-center justify-between gap-6 px-6">
          <div className="flex items-center gap-8">
            <NavLink to="/" className="flex items-center gap-2">
              <div className="flex h-7 w-7 items-center justify-center rounded-md border border-border/80 bg-card shadow-sm">
                <GitPullRequest className="h-3.5 w-3.5 text-foreground" />
              </div>
              <span className="text-sm font-semibold tracking-tight">
                FluxGuardian
              </span>
            </NavLink>
            <nav className="hidden items-center gap-1 md:flex">
              {navItems.map(({ to, label, icon: Icon, end }) => (
                <NavLink
                  key={to}
                  to={to}
                  end={end}
                  className={({ isActive }) =>
                    cn(
                      "flex items-center gap-2 rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
                      isActive
                        ? "bg-accent text-foreground"
                        : "text-muted-foreground hover:bg-accent/60 hover:text-foreground",
                    )
                  }
                >
                  <Icon className="h-3.5 w-3.5" />
                  {label}
                </NavLink>
              ))}
            </nav>
          </div>
          <div className="flex items-center gap-2">
            <ThemeToggle />
          </div>
        </div>
      </header>

      <main className="flex-1 animate-fade-in">
        <Outlet />
      </main>

      <footer className="border-t border-border/60 py-6">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-6 text-xs text-muted-foreground">
          <span>© {new Date().getFullYear()} FluxGuardian</span>
          <span className="font-mono">v0.1.0</span>
        </div>
      </footer>
    </div>
  );
}
