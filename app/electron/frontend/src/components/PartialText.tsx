import { useState, useCallback, useRef } from 'react';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';
import { Edit2, Check, X, Sparkles } from 'lucide-react';

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export type PartialTextProps = {
  /** The partial text content */
  text: string;
  /** Confidence score from 0 to 1 */
  confidence?: number;
  /** Whether this is still being transcribed */
  isDraft?: boolean;
  /** Timestamp of the partial */
  timestamp?: number;
  /** Called when user edits the text */
  onEdit?: (newText: string) => void;
  /** Called when user accepts the partial as final */
  onAccept?: () => void;
  /** Called when user dismisses the partial */
  onDismiss?: () => void;
  /** Additional CSS classes */
  className?: string;
  /** Whether to show confidence indicator */
  showConfidence?: boolean;
  /** Animation variant */
  animation?: 'pulse' | 'fade' | 'none';
};

export function PartialText({
  text,
  confidence = 0.5,
  isDraft = true,
  timestamp,
  onEdit,
  onAccept,
  onDismiss,
  className,
  showConfidence = true,
  animation = 'pulse',
}: PartialTextProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [editValue, setEditValue] = useState(text);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleStartEdit = useCallback(() => {
    if (!onEdit) return;
    setEditValue(text);
    setIsEditing(true);
    // Focus input after render
    setTimeout(() => inputRef.current?.focus(), 0);
  }, [onEdit, text]);

  const handleSaveEdit = useCallback(() => {
    if (editValue.trim() !== text.trim()) {
      onEdit?.(editValue.trim());
    }
    setIsEditing(false);
  }, [editValue, text, onEdit]);

  const handleCancelEdit = useCallback(() => {
    setEditValue(text);
    setIsEditing(false);
  }, [text]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleSaveEdit();
    } else if (e.key === 'Escape') {
      handleCancelEdit();
    }
  }, [handleSaveEdit, handleCancelEdit]);

  // Get confidence color
  const getConfidenceColor = (conf: number): string => {
    if (conf >= 0.8) return 'text-green-500';
    if (conf >= 0.6) return 'text-yellow-500';
    if (conf >= 0.4) return 'text-orange-500';
    return 'text-red-500';
  };

  // Get confidence label
  const getConfidenceLabel = (conf: number): string => {
    if (conf >= 0.8) return 'High confidence';
    if (conf >= 0.6) return 'Medium confidence';
    if (conf >= 0.4) return 'Low confidence';
    return 'Very low confidence';
  };

  // Format timestamp
  const formatTime = (ms?: number): string => {
    if (!ms) return '';
    const seconds = Math.floor(ms / 1000);
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const animationClasses = {
    pulse: 'animate-pulse',
    fade: 'animate-fade-in',
    none: '',
  };

  if (isEditing) {
    return (
      <div 
        className={cn(
          'flex items-center gap-2 p-2 rounded-md bg-lawn-panel border-2 border-lawn-accent',
          className
        )}
        role="form"
        aria-label="Edit partial text"
      >
        <input
          ref={inputRef}
          type="text"
          value={editValue}
          onChange={(e) => setEditValue(e.target.value)}
          onKeyDown={handleKeyDown}
          className="flex-1 bg-lawn-bg border-2 border-lawn-border px-3 py-1 text-sm text-lawn-border focus:border-lawn-accent focus:outline-none rounded"
          aria-label="Edit transcription text"
        />
        <button
          onClick={handleSaveEdit}
          className="p-1.5 rounded hover:bg-green-500/20 text-green-500 transition-colors"
          aria-label="Save edit"
          title="Save (Enter)"
        >
          <Check className="w-4 h-4" />
        </button>
        <button
          onClick={handleCancelEdit}
          className="p-1.5 rounded hover:bg-red-500/20 text-red-500 transition-colors"
          aria-label="Cancel edit"
          title="Cancel (Esc)"
        >
          <X className="w-4 h-4" />
        </button>
      </div>
    );
  }

  return (
    <div
      className={cn(
        'group relative flex items-start gap-2 p-3 rounded-md transition-all duration-200',
        isDraft 
          ? 'bg-lawn-panel/50 border-2 border-dashed border-lawn-accent/50' 
          : 'bg-lawn-panel border-2 border-lawn-border',
        animationClasses[animation],
        className
      )}
      role="article"
      aria-label={isDraft ? 'Draft transcription' : 'Confirmed transcription'}
    >
      {/* Draft indicator */}
      {isDraft && (
        <div className="flex-shrink-0 mt-0.5">
          <Sparkles 
            className={cn(
              'w-4 h-4',
              getConfidenceColor(confidence),
              animation === 'pulse' && 'animate-pulse'
            )}
            aria-hidden="true"
          />
        </div>
      )}

      {/* Text content */}
      <div className="flex-1 min-w-0">
        <p 
          className={cn(
            'text-sm leading-relaxed',
            isDraft ? 'text-lawn-border/80 italic' : 'text-lawn-border'
          )}
        >
          {text}
        </p>

        {/* Metadata row */}
        <div className="flex items-center gap-3 mt-2">
          {showConfidence && (
            <span 
              className={cn(
                'text-xs font-medium',
                getConfidenceColor(confidence)
              )}
              title={getConfidenceLabel(confidence)}
            >
              {Math.round(confidence * 100)}% confidence
            </span>
          )}
          
          {timestamp !== undefined && (
            <span className="text-xs text-lawn-muted">
              {formatTime(timestamp)}
            </span>
          )}

          {isDraft && (
            <span className="text-xs text-lawn-accent animate-pulse">
              Listening...
            </span>
          )}
        </div>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
        {onEdit && (
          <button
            onClick={handleStartEdit}
            className="p-1.5 rounded hover:bg-lawn-accent/20 text-lawn-muted hover:text-lawn-accent transition-colors"
            aria-label="Edit text"
            title="Edit"
          >
            <Edit2 className="w-3.5 h-3.5" />
          </button>
        )}
        
        {onAccept && isDraft && (
          <button
            onClick={onAccept}
            className="p-1.5 rounded hover:bg-green-500/20 text-green-500 transition-colors"
            aria-label="Accept as final"
            title="Accept"
          >
            <Check className="w-3.5 h-3.5" />
          </button>
        )}
        
        {onDismiss && (
          <button
            onClick={onDismiss}
            className="p-1.5 rounded hover:bg-red-500/20 text-red-500 transition-colors"
            aria-label="Dismiss"
            title="Dismiss"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        )}
      </div>
    </div>
  );
}

export default PartialText;
