
import { Bell, User, Clock, Train } from 'lucide-react';
import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

export function Header() {
  const navigate = useNavigate();
  const [currentTime, setCurrentTime] = useState(new Date());

  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  return (
    <header className="h-16 border-b border-border bg-card/50 backdrop-blur-sm px-6 flex items-center justify-between">
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2 text-sm">
          <Clock className="w-4 h-4 text-muted-foreground" />
          <span className="font-mono text-muted-foreground">
            {currentTime.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })}
          </span>
          <span className="font-mono text-primary font-medium">
            {currentTime.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
          </span>
        </div>
      </div>

      <div className="flex items-center gap-4">
        {/* Passenger View Button */}
        <button 
          onClick={() => navigate('/user')}
          className="flex items-center gap-2 px-3 py-1.5 bg-primary/10 hover:bg-primary/20 
                     text-primary text-sm font-medium rounded-lg transition-colors"
          title="Open Passenger View"
        >
          <Train className="w-4 h-4" />
          <span className="hidden sm:inline">Passenger View</span>
        </button>
        
        <button className="relative p-2 hover:bg-muted rounded-lg transition-colors">
          <Bell className="w-5 h-5 text-muted-foreground" />
          <span className="absolute top-1 right-1 w-2 h-2 bg-destructive rounded-full" />
        </button>
        
        <div className="flex items-center gap-3 pl-4 border-l border-border">
          <div className="w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center">
            <User className="w-4 h-4 text-primary" />
          </div>
          <div className="text-sm">
            <p className="font-medium">Control Room</p>
            <p className="text-xs text-muted-foreground">Operator</p>
          </div>
        </div>
      </div>
    </header>
  );
}
