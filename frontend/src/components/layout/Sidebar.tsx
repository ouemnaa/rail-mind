import { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { LayoutDashboard, Lightbulb, Settings, Activity, Menu, Construction, Upload } from 'lucide-react';

interface NavItem {
  path: string;
  label: string;
  icon: React.ComponentType<any>;
}

const navItems: NavItem[] = [
  { path: '/', label: 'Network Overview', icon: LayoutDashboard },
  { path: '/resolution', label: 'Resolution Options', icon: Lightbulb },
  { path: '/maintenance', label: 'Maintenance', icon: Construction },
  { path: '/documentation', label: 'Documentation', icon: Upload },
];

export function Sidebar() {
  const [isOpen, setIsOpen] = useState(true);
  const navigate = useNavigate();
  const location = useLocation();

  return (
    <div className={`h-full bg-sidebar border-r border-sidebar-border flex flex-col transition-all duration-300 ${isOpen ? 'w-64' : 'w-16'}`}>
      {/* Logo & Toggle */}
      <div className="p-4 border-b border-sidebar-border flex items-center justify-between">
        {isOpen && (
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary to-accent flex items-center justify-center">
              <Activity className="w-6 h-6 text-primary-foreground" />
            </div>
            <div>
              <h1 className="font-bold text-lg">Rail Brain</h1>
              <p className="text-xs text-muted-foreground">Decision Support</p>
            </div>
          </div>
        )}
        <button onClick={() => setIsOpen(!isOpen)} className="p-2 rounded hover:bg-muted transition-colors">
          <Menu className="w-5 h-5 text-muted-foreground" />
        </button>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-2">
        <ul className="space-y-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = location.pathname === item.path;
            return (
              <li key={item.path}>
                <button
                  onClick={() => navigate(item.path)}
                  className={`flex items-center gap-3 w-full px-4 py-3 rounded-lg text-sm font-medium transition-all duration-200 ${
                    isActive
                      ? 'bg-primary/10 text-primary border border-primary/20'
                      : 'text-muted-foreground hover:text-foreground hover:bg-muted'
                  }`}
                >
                  <Icon className={`w-5 h-5 ${isActive ? 'text-primary' : ''}`} />
                  {isOpen && item.label}
                </button>
              </li>
            );
          })}
        </ul>
      </nav>

      {/* Footer */}
      <div className="p-4 border-t border-sidebar-border">
        <button className="flex items-center gap-3 w-full px-4 py-3 rounded-lg text-sm text-muted-foreground hover:text-foreground hover:bg-muted transition-colors">
          <Settings className="w-5 h-5" />
          {isOpen && 'Settings'}
        </button>

        {isOpen && (
          <div className="mt-4 p-3 bg-muted/50 rounded-lg">
            <div className="flex items-center gap-2 text-xs">
              <div className="w-2 h-2 rounded-full bg-success animate-pulse" />
              <span className="text-muted-foreground">System Status:</span>
              <span className="text-success font-medium">Operational</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
