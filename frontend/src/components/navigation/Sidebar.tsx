'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { 
  Shield, 
  LayoutDashboard, 
  Target, 
  Terminal, 
  FileText, 
  AlertTriangle,
  Brain,
  Network,
  GitCommit,
  Calendar,
  Activity,
  TrendingUp,
  Server,
  Clipboard
} from 'lucide-react';

interface SidebarLinkProps {
  href: string;
  label: string;
  icon: React.ComponentType<any>;
  disabled?: boolean;
}

function SidebarLink({ href, label, icon: Icon, disabled = false }: SidebarLinkProps) {
  const pathname = usePathname();
  const isActive = pathname === href;

  if (disabled) {
    return (
      <div className="flex items-center gap-3 px-3 py-2 text-zinc-500 rounded-md cursor-not-allowed opacity-50 select-none">
        <Icon className="h-4 w-4" />
        <span className="text-sm font-medium">{label}</span>
      </div>
    );
  }

  return (
    <Link
      href={href}
      className={`flex items-center gap-3 px-3 py-2 rounded-md transition-all duration-200 ${
        isActive
          ? 'bg-indigo-600/20 text-indigo-400 border-l-2 border-indigo-500 font-semibold'
          : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900/50'
      }`}
    >
      <Icon className={`h-4 w-4 ${isActive ? 'text-indigo-400' : 'text-zinc-400'}`} />
      <span className="text-sm font-medium">{label}</span>
    </Link>
  );
}

export function Sidebar() {
  return (
    <aside className="w-64 bg-zinc-950 border-r border-zinc-900 flex flex-col h-full select-none">
      {/* Brand Header */}
      <div className="h-16 flex items-center px-6 gap-2 border-b border-zinc-900 bg-zinc-950/80 backdrop-blur-md">
        <Shield className="h-6 w-6 text-indigo-500 animate-pulse" />
        <span className="font-bold text-lg text-white tracking-wide">AegisX</span>
      </div>

      {/* Navigation Groups */}
      <div className="flex-1 overflow-y-auto px-4 py-6 space-y-8">
        <div>
          <div className="px-3 mb-2 text-xs font-semibold text-zinc-500 uppercase tracking-wider">
            General
          </div>
          <div className="space-y-1">
            <SidebarLink href="/" label="Dashboard" icon={LayoutDashboard} />
            <SidebarLink href="/scopes" label="Scopes" icon={Target} />
            <SidebarLink href="/assets" label="Assets Inventory" icon={Terminal} />
          </div>
        </div>

        <div>
          <div className="px-3 mb-2 text-xs font-semibold text-zinc-500 uppercase tracking-wider">
            Operations
          </div>
          <div className="space-y-1">
            <SidebarLink href="/findings" label="Findings Log" icon={AlertTriangle} />
            <SidebarLink href="/workflows" label="Scan Workflows" icon={GitCommit} />
            <SidebarLink href="/planning" label="Remediation Plans" icon={Calendar} />
            <SidebarLink href="/reports" label="Reports & Exports" icon={FileText} />
            <SidebarLink href="/soc" label="SOC Operations" icon={Activity} />
          </div>
        </div>

        <div>
          <div className="px-3 mb-2 text-xs font-semibold text-zinc-500 uppercase tracking-wider">
            Intelligence
          </div>
          <div className="space-y-1">
            <SidebarLink href="/threat-intel" label="Threat Intel" icon={Brain} />
            <SidebarLink href="/graph" label="Topology Graph" icon={Network} />
            <SidebarLink href="/grc" label="GRC Compliance" icon={Shield} />
            <SidebarLink href="/executive" label="Executive Posture" icon={TrendingUp} />
            <SidebarLink href="/whiteboards" label="Saved Whiteboards" icon={Clipboard} />
          </div>
        </div>

        <div>
          <div className="px-3 mb-2 text-xs font-semibold text-zinc-500 uppercase tracking-wider">
            Administration
          </div>
          <div className="space-y-1">
            <SidebarLink href="/admin/sso" label="SSO & Tenants" icon={Server} />
          </div>
        </div>
      </div>

      {/* Footer System Status */}
      <div className="p-4 border-t border-zinc-900 bg-zinc-950/40 text-center">
        <span className="text-[10px] text-zinc-600 font-mono tracking-wider">
          v1.0.0-PROD
        </span>
      </div>
    </aside>
  );
}
