import {
  ActivityIcon,
  FolderKanbanIcon,
  HistoryIcon,
  LayoutDashboardIcon,
  LightbulbIcon,
  MessageSquareTextIcon,
  SettingsIcon,
  SparklesIcon,
  WrenchIcon,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  title: string;
  href: string;
  icon: LucideIcon;
  /** Whether the page's data follows the date range. */
  ranged: boolean;
}

export const MAIN_NAV: NavItem[] = [
  { title: "Overview", href: "/overview", icon: LayoutDashboardIcon, ranged: true },
  { title: "Activity", href: "/activity", icon: ActivityIcon, ranged: true },
  { title: "Prompts", href: "/prompts", icon: MessageSquareTextIcon, ranged: true },
  { title: "Sessions", href: "/sessions", icon: HistoryIcon, ranged: true },
  { title: "Projects", href: "/projects", icon: FolderKanbanIcon, ranged: true },
  { title: "Tools", href: "/tools", icon: WrenchIcon, ranged: true },
  { title: "Skills", href: "/skills", icon: SparklesIcon, ranged: true },
  { title: "Tips", href: "/tips", icon: LightbulbIcon, ranged: false },
];

export const SETTINGS_NAV: NavItem = { title: "Settings", href: "/settings", icon: SettingsIcon, ranged: false };

export const ALL_NAV = [...MAIN_NAV, SETTINGS_NAV];

/** The nav item for a pathname (`/sessions/abc` → Sessions). */
export function navItemFor(pathname: string): NavItem | undefined {
  return ALL_NAV.find((item) => pathname === item.href || pathname.startsWith(`${item.href}/`));
}
