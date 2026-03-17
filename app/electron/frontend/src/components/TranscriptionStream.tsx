/**
 * TranscriptionStream - Real-time transcription display with segment management
 * 
 * Renders live transcript segments with audio visualization, search, export (txt/json/srt),
 * and segment editing capabilities. Integrates WebSocket for real-time updates.
 * 
 * @component
 */
import { 
  useState, 
  useRef, 
  useCallback, 
  useEffect, 
  useMemo,
  useImperativeHandle,
  forwardRef,
  memo,
} from 'react';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';
import { 
  Search, 
  Download, 
  Copy, 
  Trash2, 
  ChevronDown,
  Wifi,
  WifiOff,
  AlertCircle,
  Check,
  X,
  Clock,
  Mic,
  Type,
} from 'lucide-react';
import type { Segment, Word } from '../types/api';
import { PartialText } from './PartialText';
import { AudioVisualizer } from './AudioVisualizer';
import { useWebSocket, type WebSocketMessage } from '../hooks/useWebSocket';
import { ErrorBoundary } from './ErrorBoundary';

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

// ============================================
// Types
// ============================================

export type TranscriptionStreamRef = {
  scrollToBottom: () => void;
  scrollToSegment: (segmentId: string) => void;
  getTranscriptText: () => string;
  exportTranscript: (format: 'txt' | 'json' | 'srt') => string;
  clearSearch: () => void;
};

export type TranscriptionStreamProps = {
  /** Array of transcription segments */
  segments: Segment[];
  /** Current partial/draft text being transcribed */
  partialText?: string | null;
  /** Partial text confidence */
  partialConfidence?: number;
  /** Audio level for visualization (0-1) */
  audioLevel?: number;
  /** Audio frequency data for spectrum */
  frequencyData?: number[] | null;
  /** Whether transcription is active */
  isRecording?: boolean;
  /** WebSocket URL for real-time updates */
  wsUrl?: string;
  /** Current session ID */
  sessionId?: string | null;
  /** Additional CSS classes */
  className?: string;
  /** Called when a segment is edited */
  onSegmentEdit?: (segmentId: string, newText: string) => void;
  /** Called when a segment is deleted */
  onSegmentDelete?: (segmentId: string) => void;
  /** Called when a segment is copied */
  onSegmentCopy?: (segmentId: string) => void;
  /** Called when export is requested */
  onExport?: (format: 'txt' | 'json' | 'srt', content: string) => void;
  /** Called when user requests scroll to bottom */
  onScrollToBottom?: () => void;
};

type DisplaySegment = Segment & {
  searchHighlight?: boolean;
};

// ============================================
// Utility Functions
// ============================================

function formatTimestamp(ms: number): string {
  const seconds = Math.floor(ms / 1000);
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  const msPart = Math.floor((ms % 1000) / 10);
  return `${mins}:${secs.toString().padStart(2, '0')}.${msPart.toString().padStart(2, '0')}`;
}

function formatDuration(start: number, end: number): string {
  const duration = end - start;
  return `${(duration / 1000).toFixed(1)}s`;
}

function getConfidenceColor(confidence: number): string {
  if (confidence >= 0.8) return 'bg-green-500';
  if (confidence >= 0.6) return 'bg-yellow-500';
  if (confidence >= 0.4) return 'bg-orange-500';
  return 'bg-red-500';
}

function getConfidenceLabel(confidence: number): string {
  if (confidence >= 0.8) return 'High';
  if (confidence >= 0.6) return 'Medium';
  if (confidence >= 0.4) return 'Low';
  return 'Very Low';
}

function exportToSrt(segments: Segment[]): string {
  return segments
    .map((seg, index) => {
      const start = new Date(seg.start).toISOString().substr(11, 12).replace('.', ',');
      const end = new Date(seg.end).toISOString().substr(11, 12).replace('.', ',');
      return `${index + 1}\n${start} --> ${end}\n${seg.text}\n`;
    })
    .join('\n');
}

function exportToTxt(segments: Segment[]): string {
  return segments.map(s => s.text).join('\n\n');
}

function exportToJson(segments: Segment[]): string {
  return JSON.stringify(segments, null, 2);
}

// ============================================
// Sub-components
// ============================================

const WordTooltip = memo(function WordTooltip({ word }: { word: Word }) {
  return (
    <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1 px-2 py-1 bg-lawn-bg border border-lawn-border rounded text-xs whitespace-nowrap z-10 shadow-lg">
      <div className="font-medium">{word.text}</div>
      <div className="text-lawn-muted">
        {formatTimestamp(word.start)} - {formatTimestamp(word.end)}
      </div>
      <div className={cn('font-medium', 
        word.confidence >= 0.8 ? 'text-green-500' :
        word.confidence >= 0.6 ? 'text-yellow-500' :
        word.confidence >= 0.4 ? 'text-orange-500' : 'text-red-500'
      )}>
        {Math.round(word.confidence * 100)}% confidence
      </div>
    </div>
  );
});

const SegmentWords = memo(function SegmentWords({ 
  words, 
  segmentId,
  onEdit: _onEdit,
}: { 
  words: Word[]; 
  segmentId: string;
  onEdit?: (segmentId: string, newText: string) => void;
}) {
  const [hoveredWord, setHoveredWord] = useState<number | null>(null);

  return (
    <span className="inline-flex flex-wrap gap-0.5">
      {words.map((word, idx) => (
        <span
          key={`${segmentId}-word-${idx}`}
          className={cn(
            'relative cursor-help px-0.5 rounded transition-colors',
            word.confidence >= 0.8 ? 'hover:bg-green-500/10' :
            word.confidence >= 0.6 ? 'hover:bg-yellow-500/10' :
            word.confidence >= 0.4 ? 'hover:bg-orange-500/10' : 'hover:bg-red-500/10'
          )}
          onMouseEnter={() => setHoveredWord(idx)}
          onMouseLeave={() => setHoveredWord(null)}
        >
          {word.text}
          {hoveredWord === idx && <WordTooltip word={word} />}
        </span>
      ))}
    </span>
  );
});

const SegmentItem = memo(forwardRef<HTMLDivElement, {
  segment: DisplaySegment;
  onEdit?: (segmentId: string, newText: string) => void;
  onDelete?: (segmentId: string) => void;
  onCopy?: (segmentId: string) => void;
  isLast?: boolean;
}>(function SegmentItem({ segment, onEdit: _onEdit, onDelete, onCopy, isLast }, ref) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [showActions, setShowActions] = useState(false);
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(segment.text);
    setCopied(true);
    onCopy?.(segment.id);
    setTimeout(() => setCopied(false), 2000);
  }, [segment.text, segment.id, onCopy]);

  return (
    <div
      ref={ref}
      data-segment-id={segment.id}
      className={cn(
        'group relative p-4 rounded-lg border-2 transition-all duration-200',
        segment.searchHighlight 
          ? 'bg-yellow-500/10 border-yellow-500/50' 
          : 'bg-lawn-panel border-lawn-border hover:border-lawn-accent/50',
        isLast && 'mb-4'
      )}
      onMouseEnter={() => setShowActions(true)}
      onMouseLeave={() => setShowActions(false)}
      role="article"
      aria-label={`Transcription segment from ${formatTimestamp(segment.start)}`}
    >
      {/* Segment header */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="text-xs font-mono text-lawn-muted">
            {formatTimestamp(segment.start)}
          </span>
          <span className="text-xs text-lawn-muted">-</span>
          <span className="text-xs font-mono text-lawn-muted">
            {formatTimestamp(segment.end)}
          </span>
          <span className="text-xs text-lawn-muted">
            ({formatDuration(segment.start, segment.end)})
          </span>
        </div>

        <div className="flex items-center gap-2">
          {/* Confidence indicator */}
          <div 
            className="flex items-center gap-1"
            title={`${getConfidenceLabel(segment.confidence)} confidence`}
          >
            <div className={cn('w-2 h-2 rounded-full', getConfidenceColor(segment.confidence))} />
            <span className="text-xs text-lawn-muted">
              {Math.round(segment.confidence * 100)}%
            </span>
          </div>

          {/* Language badge */}
          <span className="text-xs px-1.5 py-0.5 rounded bg-lawn-bg border border-lawn-border text-lawn-muted uppercase">
            {segment.language}
          </span>

          {/* Actions */}
          <div className={cn(
            'flex items-center gap-1 transition-opacity',
            showActions ? 'opacity-100' : 'opacity-0'
          )}>
            <button
              onClick={handleCopy}
              className={cn(
                'p-1.5 rounded transition-colors',
                copied ? 'text-green-500' : 'text-lawn-muted hover:text-lawn-accent'
              )}
              title={copied ? 'Copied!' : 'Copy text'}
              aria-label="Copy segment text"
            >
              {copied ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
            </button>
            <button
              onClick={() => onDelete?.(segment.id)}
              className="p-1.5 rounded text-lawn-muted hover:text-red-500 transition-colors"
              title="Delete segment"
              aria-label="Delete segment"
            >
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>

      {/* Segment text */}
      <div className="text-sm text-lawn-border leading-relaxed">
        {segment.words && segment.words.length > 0 ? (
          <SegmentWords words={segment.words} segmentId={segment.id} />
        ) : (
          <span>{segment.display_text || segment.text}</span>
        )}
      </div>

      {/* Quality indicators */}
      {(segment.review_flag || segment.suppressed) && (
        <div className="flex items-center gap-2 mt-2">
          {segment.review_flag && (
            <span className="text-xs px-2 py-0.5 rounded bg-yellow-500/10 text-yellow-600 border border-yellow-500/30">
              Needs Review
            </span>
          )}
          {segment.suppressed && (
            <span className="text-xs px-2 py-0.5 rounded bg-red-500/10 text-red-600 border border-red-500/30">
              Suppressed
            </span>
          )}
        </div>
      )}

      {/* Expandable details */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="mt-2 text-xs text-lawn-muted hover:text-lawn-accent flex items-center gap-1 transition-colors"
        aria-expanded={isExpanded}
      >
        <ChevronDown className={cn('w-3 h-3 transition-transform', isExpanded && 'rotate-180')} />
        {isExpanded ? 'Less details' : 'More details'}
      </button>

      {isExpanded && (
        <div className="mt-3 pt-3 border-t border-lawn-border/30 text-xs text-lawn-muted space-y-1">
          <div className="flex justify-between">
            <span>Quality:</span>
            <span className="text-lawn-border">{segment.quality_label}</span>
          </div>
          <div className="flex justify-between">
            <span>Script Mismatch:</span>
            <span className={segment.script_mismatch ? 'text-red-500' : 'text-green-500'}>
              {segment.script_mismatch ? 'Yes' : 'No'}
            </span>
          </div>
          {segment.latency_ms !== undefined && (
            <div className="flex justify-between">
              <span>Latency:</span>
              <span className="text-lawn-border">{segment.latency_ms}ms</span>
            </div>
          )}
          {segment.avg_logprob !== undefined && segment.avg_logprob !== null && (
            <div className="flex justify-between">
              <span>Avg LogProb:</span>
              <span className="text-lawn-border">{segment.avg_logprob.toFixed(3)}</span>
            </div>
          )}
          {segment.no_speech_prob !== undefined && segment.no_speech_prob !== null && (
            <div className="flex justify-between">
              <span>No Speech Prob:</span>
              <span className="text-lawn-border">{(segment.no_speech_prob * 100).toFixed(1)}%</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}));

const ConnectionStatus = memo(function ConnectionStatus({ 
  status, 
  reconnectAttempts 
}: { 
  status: ReturnType<typeof useWebSocket>['status'];
  reconnectAttempts: number;
}) {
  const statusConfig = {
    connecting: { icon: Wifi, color: 'text-yellow-500', text: 'Connecting...' },
    open: { icon: Wifi, color: 'text-green-500', text: 'Connected' },
    closing: { icon: WifiOff, color: 'text-yellow-500', text: 'Closing...' },
    closed: { icon: WifiOff, color: 'text-lawn-muted', text: 'Disconnected' },
    reconnecting: { icon: AlertCircle, color: 'text-orange-500', text: `Reconnecting (${reconnectAttempts})` },
    error: { icon: AlertCircle, color: 'text-red-500', text: 'Connection Error' },
  };

  const config = statusConfig[status];
  const Icon = config.icon;

  return (
    <div className={cn('flex items-center gap-1.5 text-xs', config.color)}>
      <Icon className="w-3.5 h-3.5" />
      <span>{config.text}</span>
    </div>
  );
});

// ============================================
// Main Component
// ============================================

export const TranscriptionStream = forwardRef<TranscriptionStreamRef, TranscriptionStreamProps>(
  function TranscriptionStream({
    segments,
    partialText,
    partialConfidence = 0.5,
    audioLevel = 0,
    frequencyData,
    isRecording = false,
    wsUrl = '/api/ws',
    sessionId: _sessionId,
    className,
    onSegmentEdit,
    onSegmentDelete,
    onSegmentCopy,
    onExport,
    onScrollToBottom,
  }, ref) {
    // State
    const [searchQuery, setSearchQuery] = useState('');
    const [isSearchFocused, setIsSearchFocused] = useState(false);
    const [autoScroll, setAutoScroll] = useState(true);
    const [filterConfidence, setFilterConfidence] = useState<number | null>(null);
    const [showAudioVisualizer, setShowAudioVisualizer] = useState(true);
    const [exportFormat, setExportFormat] = useState<'txt' | 'json' | 'srt'>('txt');
    const [copiedAll, setCopiedAll] = useState(false);

    // Refs
    const containerRef = useRef<HTMLDivElement>(null);
    const scrollContainerRef = useRef<HTMLDivElement>(null);
    const segmentRefs = useRef<Map<string, HTMLDivElement>>(new Map());
    const lastSegmentCount = useRef(segments.length);
    const isUserScrolling = useRef(false);
    const scrollTimeout = useRef<number | null>(null);

    // WebSocket connection for real-time updates
    const { status: wsStatus, reconnectAttempts } = useWebSocket({
      url: wsUrl,
      maxReconnectAttempts: 5,
      bufferMessages: true,
      onMessage: (message: WebSocketMessage) => {
        // Handle real-time transcription updates
        console.debug('WebSocket message:', message);
      },
    });

    // Filter and search segments
    const displaySegments = useMemo((): DisplaySegment[] => {
      let result = segments.map(s => ({ ...s, searchHighlight: false }));

      // Apply confidence filter
      if (filterConfidence !== null) {
        result = result.filter(s => s.confidence >= filterConfidence);
      }

      // Apply search
      if (searchQuery.trim()) {
        const query = searchQuery.toLowerCase();
        result = result.map(s => ({
          ...s,
          searchHighlight: s.text.toLowerCase().includes(query) || 
                          s.display_text?.toLowerCase().includes(query),
        }));
      }

      return result;
    }, [segments, searchQuery, filterConfidence]);

    // Exposed imperative methods
    useImperativeHandle(ref, () => ({
      scrollToBottom: () => {
        scrollContainerRef.current?.scrollTo({
          top: scrollContainerRef.current.scrollHeight,
          behavior: 'smooth',
        });
      },
      scrollToSegment: (segmentId: string) => {
        const element = segmentRefs.current.get(segmentId);
        if (element) {
          element.scrollIntoView({ behavior: 'smooth', block: 'center' });
          element.classList.add('ring-2', 'ring-lawn-accent');
          setTimeout(() => {
            element.classList.remove('ring-2', 'ring-lawn-accent');
          }, 2000);
        }
      },
      getTranscriptText: () => {
        return segments.map(s => s.text).join('\n\n');
      },
      exportTranscript: (format: 'txt' | 'json' | 'srt') => {
        switch (format) {
          case 'srt':
            return exportToSrt(segments);
          case 'json':
            return exportToJson(segments);
          case 'txt':
          default:
            return exportToTxt(segments);
        }
      },
      clearSearch: () => {
        setSearchQuery('');
      },
    }), [segments]);

    // Auto-scroll when new segments arrive
    useEffect(() => {
      if (segments.length > lastSegmentCount.current && autoScroll && !isUserScrolling.current) {
        scrollContainerRef.current?.scrollTo({
          top: scrollContainerRef.current.scrollHeight,
          behavior: 'smooth',
        });
        onScrollToBottom?.();
      }
      lastSegmentCount.current = segments.length;
    }, [segments.length, autoScroll, onScrollToBottom]);

    // Cleanup scroll timeout on unmount
    useEffect(() => {
      return () => {
        if (scrollTimeout.current) {
          window.clearTimeout(scrollTimeout.current);
        }
      };
    }, []);

    // Handle user scroll detection
    const handleScroll = useCallback(() => {
      isUserScrolling.current = true;
      if (scrollTimeout.current) {
        window.clearTimeout(scrollTimeout.current);
      }
      scrollTimeout.current = window.setTimeout(() => {
        isUserScrolling.current = false;
      }, 150);

      // Check if near bottom for auto-scroll toggle
      const container = scrollContainerRef.current;
      if (container) {
        const isNearBottom = container.scrollHeight - container.scrollTop - container.clientHeight < 100;
        setAutoScroll(isNearBottom);
      }
    }, []);

    // Export handlers
    const handleExport = useCallback(() => {
      const content = (() => {
        switch (exportFormat) {
          case 'srt':
            return exportToSrt(segments);
          case 'json':
            return exportToJson(segments);
          case 'txt':
          default:
            return exportToTxt(segments);
        }
      })();
      onExport?.(exportFormat, content);
    }, [exportFormat, segments, onExport]);

    const handleCopyAll = useCallback(() => {
      const text = segments.map(s => s.text).join('\n\n');
      navigator.clipboard.writeText(text);
      setCopiedAll(true);
      setTimeout(() => setCopiedAll(false), 2000);
    }, [segments]);

    const handleClearSearch = useCallback(() => {
      setSearchQuery('');
    }, []);

    // Stats
    const stats = useMemo(() => {
      const totalDuration = segments.reduce((acc, s) => acc + (s.end - s.start), 0);
      const avgConfidence = segments.length > 0
        ? segments.reduce((acc, s) => acc + s.confidence, 0) / segments.length
        : 0;
      
      return {
        segmentCount: segments.length,
        totalDuration,
        avgConfidence,
        highlightedCount: displaySegments.filter(s => s.searchHighlight).length,
      };
    }, [segments, displaySegments]);

    return (
      <ErrorBoundary>
        <div 
          ref={containerRef}
          className={cn(
            'flex flex-col h-full bg-lawn-bg border-2 border-lawn-border rounded-lg overflow-hidden',
            className
          )}
        >
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b-2 border-lawn-border bg-lawn-panel">
            <div className="flex items-center gap-3">
              <Type className="w-5 h-5 text-lawn-accent" />
              <h2 className="font-bold text-lawn-border">Transcription</h2>
              
              {/* Stats */}
              <div className="hidden sm:flex items-center gap-2 text-xs text-lawn-muted">
                <span>{stats.segmentCount} segments</span>
                <span>·</span>
                <span>{(stats.totalDuration / 1000 / 60).toFixed(1)} min</span>
                <span>·</span>
                <span className={cn(
                  stats.avgConfidence >= 0.8 ? 'text-green-500' :
                  stats.avgConfidence >= 0.6 ? 'text-yellow-500' : 'text-orange-500'
                )}>
                  {Math.round(stats.avgConfidence * 100)}% avg confidence
                </span>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <ConnectionStatus status={wsStatus} reconnectAttempts={reconnectAttempts} />
            </div>
          </div>

          {/* Toolbar */}
          <div className="flex flex-wrap items-center gap-2 px-4 py-2 border-b border-lawn-border/50 bg-lawn-panel/50">
            {/* Search */}
            <div className={cn(
              'relative flex items-center flex-1 min-w-[200px] max-w-md',
              isSearchFocused && 'z-10'
            )}>
              <Search className="absolute left-2.5 w-4 h-4 text-lawn-muted" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onFocus={() => setIsSearchFocused(true)}
                onBlur={() => setIsSearchFocused(false)}
                placeholder="Search transcript..."
                className={cn(
                  'w-full pl-9 pr-8 py-1.5 text-sm bg-lawn-bg border-2 border-lawn-border rounded',
                  'text-lawn-border placeholder:text-lawn-muted',
                  'focus:border-lawn-accent focus:outline-none transition-colors'
                )}
                aria-label="Search transcript"
              />
              {searchQuery && (
                <button
                  onClick={handleClearSearch}
                  className="absolute right-2 p-0.5 rounded hover:bg-lawn-border/20 text-lawn-muted"
                  aria-label="Clear search"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              )}
            </div>

            {/* Search results indicator */}
            {searchQuery && stats.highlightedCount > 0 && (
              <span className="text-xs text-yellow-500">
                {stats.highlightedCount} matches
              </span>
            )}

            {/* Spacer */}
            <div className="flex-1" />

            {/* Filter */}
            <select
              value={filterConfidence ?? ''}
              onChange={(e) => setFilterConfidence(e.target.value ? Number(e.target.value) : null)}
              className="px-2 py-1.5 text-xs bg-lawn-bg border-2 border-lawn-border rounded text-lawn-border focus:border-lawn-accent focus:outline-none"
              aria-label="Filter by confidence"
              title="Filter by confidence"
            >
              <option value="">All confidence</option>
              <option value="0.8">High (80%+)</option>
              <option value="0.6">Medium (60%+)</option>
              <option value="0.4">Low (40%+)</option>
            </select>

            {/* Audio visualizer toggle */}
            <button
              onClick={() => setShowAudioVisualizer(!showAudioVisualizer)}
              className={cn(
                'p-1.5 rounded transition-colors',
                showAudioVisualizer ? 'text-lawn-accent bg-lawn-accent/10' : 'text-lawn-muted hover:text-lawn-accent'
              )}
              title={showAudioVisualizer ? 'Hide audio visualizer' : 'Show audio visualizer'}
              aria-label={showAudioVisualizer ? 'Hide audio visualizer' : 'Show audio visualizer'}
            >
              <Mic className="w-4 h-4" />
            </button>

            {/* Copy all */}
            <button
              onClick={handleCopyAll}
              className={cn(
                'flex items-center gap-1.5 px-3 py-1.5 text-xs rounded border-2 transition-colors',
                copiedAll 
                  ? 'bg-green-500/10 border-green-500 text-green-500' 
                  : 'border-lawn-border text-lawn-muted hover:border-lawn-accent hover:text-lawn-accent'
              )}
            >
              {copiedAll ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
              <span className="hidden sm:inline">{copiedAll ? 'Copied!' : 'Copy All'}</span>
            </button>

            {/* Export */}
            <div className="flex items-center">
              <select
                value={exportFormat}
                onChange={(e) => setExportFormat(e.target.value as 'txt' | 'json' | 'srt')}
                className="px-2 py-1.5 text-xs bg-lawn-bg border-2 border-r-0 border-lawn-border rounded-l text-lawn-border focus:border-lawn-accent focus:outline-none"
                aria-label="Export format"
              >
                <option value="txt">TXT</option>
                <option value="json">JSON</option>
                <option value="srt">SRT</option>
              </select>
              <button
                onClick={handleExport}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-r border-2 border-lawn-border bg-lawn-accent text-lawn-bg hover:bg-lawn-accent/90 transition-colors"
              >
                <Download className="w-3.5 h-3.5" />
                <span className="hidden sm:inline">Export</span>
              </button>
            </div>
          </div>

          {/* Audio Visualizer */}
          {showAudioVisualizer && (
            <div className="px-4 py-2 border-b border-lawn-border/30">
              <AudioVisualizer
                level={audioLevel}
                frequencyData={frequencyData}
                isActive={isRecording}
                variant="bars"
                color={isRecording ? 'success' : 'default'}
                height={40}
              />
            </div>
          )}

          {/* Transcript content */}
          <div
            ref={scrollContainerRef}
            onScroll={handleScroll}
            className="flex-1 overflow-y-auto p-4 space-y-3 scroll-smooth"
            role="log"
            aria-live="polite"
            aria-atomic="false"
            aria-label="Transcription segments"
          >
            {/* Empty state */}
            {segments.length === 0 && !partialText && (
              <div className="flex flex-col items-center justify-center h-48 text-lawn-muted">
                <Mic className="w-12 h-12 mb-4 opacity-30" />
                <p className="text-sm">No transcription yet</p>
                <p className="text-xs mt-1">Start recording to see text appear here</p>
              </div>
            )}

            {/* Segments */}
            {displaySegments.map((segment, index) => (
              <SegmentItem
                key={segment.id}
                ref={(el) => {
                  if (el) {
                    segmentRefs.current.set(segment.id, el);
                  }
                }}
                segment={segment}
                onEdit={onSegmentEdit}
                onDelete={onSegmentDelete}
                onCopy={onSegmentCopy}
                isLast={index === displaySegments.length - 1}
              />
            ))}

            {/* Partial text */}
            {partialText && (
              <PartialText
                text={partialText}
                confidence={partialConfidence}
                isDraft={true}
                showConfidence={true}
                animation="pulse"
              />
            )}
          </div>

          {/* Footer */}
          <div className="flex items-center justify-between px-4 py-2 border-t-2 border-lawn-border bg-lawn-panel text-xs">
            <div className="flex items-center gap-4 text-lawn-muted">
              <label className="flex items-center gap-2 cursor-pointer hover:text-lawn-border transition-colors">
                <input
                  type="checkbox"
                  checked={autoScroll}
                  onChange={(e) => setAutoScroll(e.target.checked)}
                  className="rounded border-lawn-border"
                />
                Auto-scroll
              </label>
              {isRecording && (
                <span className="flex items-center gap-1.5 text-green-500">
                  <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
                  Recording
                </span>
              )}
            </div>

            <div className="flex items-center gap-3 text-lawn-muted">
              {wsStatus === 'open' && (
                <span className="flex items-center gap-1.5">
                  <Clock className="w-3.5 h-3.5" />
                  Real-time
                </span>
              )}
              <span>{segments.length} segments</span>
            </div>
          </div>
        </div>
      </ErrorBoundary>
    );
  }
);

export default TranscriptionStream;
