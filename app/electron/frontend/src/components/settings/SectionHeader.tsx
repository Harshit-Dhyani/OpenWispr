interface SectionHeaderProps {
  title: string;
  icon: React.ElementType;
  description?: string;
}

export function SectionHeader({ title, icon: Icon, description }: SectionHeaderProps) {
  return (
    <div className="mb-6 pb-4 border-b-2 border-lawn-border">
      <div className="flex items-center gap-3 mb-2">
        <Icon className="w-5 h-5 text-lawn-accent" />
        <h3 className="text-lg font-black uppercase tracking-wider">{title}</h3>
      </div>
      {description && (
        <p className="text-sm text-stone-500">{description}</p>
      )}
    </div>
  );
}
