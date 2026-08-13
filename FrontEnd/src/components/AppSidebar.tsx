import { Link } from "@tanstack/react-router";
import { FilePlus2, Files, ShieldCheck, ChevronLeft, ChevronRight } from "lucide-react";
import { useState, useEffect, useRef } from "react";

const items = [
  { to: "/", label: "Scrape New", icon: FilePlus2 },
  { to: "/files", label: "Files", icon: Files },
  { to: "/policies", label: "Policies", icon: ShieldCheck },
] as const;

const STORAGE_KEY = "sidebar-collapsed";
const USER_NAME_KEY = "user-name";

export function AppSidebar() {
  const [collapsed, setCollapsed] = useState(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      return stored ? JSON.parse(stored) : false;
    } catch {
      return false;
    }
  });

  const [userName, setUserName] = useState(() => {
    try {
      return localStorage.getItem(USER_NAME_KEY) || "User";
    } catch {
      return "User";
    }
  });

  const [isEditing, setIsEditing] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(collapsed));
    } catch {
      /* ignore */
    }
  }, [collapsed]);

  useEffect(() => {
    try {
      localStorage.setItem(USER_NAME_KEY, userName);
    } catch {
      /* ignore */
    }
  }, [userName]);

  // Focus input when editing starts
  useEffect(() => {
    if (isEditing && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [isEditing]);

  const toggle = () => setCollapsed((prev: boolean) => !prev);

  const handleNameClick = () => {
    if (!collapsed) setIsEditing(true);
  };

  const handleNameChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setUserName(e.target.value);
  };

  const handleNameBlur = () => {
    setIsEditing(false);
    if (!userName.trim()) setUserName("User");
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      setIsEditing(false);
      if (!userName.trim()) setUserName("User");
    }
    if (e.key === "Escape") {
      setIsEditing(false);
      // revert? we could keep the current value; maybe just close without saving
      // but we already saved on each change, so it's fine.
    }
  };

  const initial = (userName.trim() || "B").charAt(0).toUpperCase();

  return (
    <aside
      className={`sticky top-0 hidden h-screen shrink-0 flex-col gap-1 border-r-2 bg-sidebar px-4 py-6 transition-all duration-300 md:flex ${
        collapsed ? "w-16" : "w-60"
      }`}
    >
      {/* Brand / Logo */}
      <div className={`mb-8 flex items-center gap-2 px-2 ${collapsed ? "justify-center" : ""}`}>
        <span className="grid h-9 w-9 place-items-center rounded-xl border-2 bg-primary font-display text-lg font-bold text-primary-foreground">
          {initial}
        </span>
        {!collapsed && (
          <div className="font-display text-lg font-semibold leading-tight">
            {isEditing ? (
              <input
                ref={inputRef}
                type="text"
                value={userName}
                onChange={handleNameChange}
                onBlur={handleNameBlur}
                onKeyDown={handleKeyDown}
                className="w-full bg-transparent outline-none"
                maxLength={20}
              />
            ) : (
              <span
                onClick={handleNameClick}
                className="cursor-pointer hover:bg-accent/20 px-1 rounded"
              >
                {userName || "User"}
              </span>
            )}
          </div>
        )}
      </div>

      {/* Navigation Items - completely hidden when collapsed */}
      {items.map(({ to, label, icon: Icon }) => (
        <Link
          key={to}
          to={to}
          activeOptions={{ exact: to === "/" }}
          className={`group flex items-center gap-3 rounded-xl px-3 py-2 text-sm font-semibold text-sidebar-foreground transition-all hover:translate-x-0.5 hover:bg-sidebar-accent data-[status=active]:border-2 data-[status=active]:bg-primary data-[status=active]:shadow-[2px_2px_0_0_var(--ink)] ${
            collapsed ? "justify-center" : ""
          }`}
        >
          {!collapsed && <Icon className="h-4 w-4 shrink-0" />}
          {!collapsed && <span>{label}</span>}
        </Link>
      ))}

      {/* Toggle button at the bottom */}
      <div className="mt-auto">
        <button
          onClick={toggle}
          className={`flex w-full items-center justify-center rounded-lg border-2 bg-card p-2 text-sm font-medium transition hover:bg-accent ${
            collapsed ? "mx-auto w-10" : ""
          }`}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
        </button>
      </div>
    </aside>
  );
}

export function MobileNav() {
  return (
    <nav className="sticky top-0 z-30 flex gap-2 border-b-2 bg-sidebar px-4 py-3 md:hidden">
      {items.map(({ to, label, icon: Icon }) => (
        <Link
          key={to}
          to={to}
          activeOptions={{ exact: to === "/" }}
          className="flex items-center gap-2 rounded-lg px-3 py-1.5 text-xs font-semibold data-[status=active]:border-2 data-[status=active]:bg-primary"
        >
          <Icon className="h-3.5 w-3.5" />
          {label}
        </Link>
      ))}
    </nav>
  );
}