import { Monitor, Cpu, Activity, HardDrive, Zap } from 'lucide-react';
import type { SystemProfile } from './types';

interface HardwareProfileDisplayProps {
  profile?: SystemProfile;
}

export function HardwareProfileDisplay({ profile }: HardwareProfileDisplayProps) {
  if (!profile) {
    return (
      <div className="border-2 border-lawn-border bg-lawn-panel p-4">
        <div className="flex items-center gap-2 text-stone-500">
          <Monitor className="w-5 h-5" />
          <span className="text-sm">No hardware profile available</span>
        </div>
      </div>
    );
  }

  return (
    <div className="border-2 border-lawn-border bg-lawn-panel p-4">
      <div className="flex items-center gap-2 mb-4">
        <Monitor className="w-5 h-5 text-lawn-accent" />
        <h4 className="text-sm font-black uppercase">System Profile</h4>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="border border-lawn-border bg-lawn-bg p-3">
          <div className="flex items-center gap-2 text-stone-500 mb-1">
            <Cpu className="w-3 h-3" />
            <span className="text-[10px] uppercase font-bold">GPU</span>
          </div>
          <span className="text-xs font-bold block truncate">
            {profile.gpu.available ? profile.gpu.name : 'CPU Only'}
          </span>
          {profile.gpu.available && (
            <span className="text-[10px] text-stone-500">{profile.gpu.vram_gb}GB VRAM</span>
          )}
        </div>
        <div className="border border-lawn-border bg-lawn-bg p-3">
          <div className="flex items-center gap-2 text-stone-500 mb-1">
            <Activity className="w-3 h-3" />
            <span className="text-[10px] uppercase font-bold">CPU</span>
          </div>
          <span className="text-xs font-bold block">{profile.cpu.cores} Cores</span>
          <span className="text-[10px] text-stone-500">{profile.cpu.ram_gb}GB RAM</span>
        </div>
        <div className="border border-lawn-border bg-lawn-bg p-3">
          <div className="flex items-center gap-2 text-stone-500 mb-1">
            <HardDrive className="w-3 h-3" />
            <span className="text-[10px] uppercase font-bold">Storage</span>
          </div>
          <span className="text-xs font-bold block">{profile.storage.free_gb}GB Free</span>
          <span className="text-[10px] text-stone-500">
            {profile.storage.ssd_available ? 'SSD' : 'HDD'}
          </span>
        </div>
        <div className="border border-lawn-border bg-lawn-bg p-3">
          <div className="flex items-center gap-2 text-stone-500 mb-1">
            <Zap className="w-3 h-3" />
            <span className="text-[10px] uppercase font-bold">Recommended</span>
          </div>
          <span className="text-xs font-bold block capitalize">{profile.recommended_quality}</span>
          <span className="text-[10px] text-lawn-accent">Preset: {profile.recommended_preset}</span>
        </div>
      </div>
    </div>
  );
}
