import { Music } from 'lucide-react';
import { useState } from 'react';

interface CoverProps {
  src?: string;
  alt: string;
  className?: string;
  iconSize?: number;
}

/** Album art with a theme-matched placeholder instead of a broken image. */
export function Cover({ src, alt, className = '', iconSize = 24 }: CoverProps) {
  // Track which src failed so a new track's art gets a fresh attempt
  const [failedSrc, setFailedSrc] = useState<string | null>(null);
  const failed = failedSrc !== null && failedSrc === src;

  if (!src || failed) {
    return (
      <div
        role="img"
        aria-label={alt}
        className={`flex items-center justify-center bg-basil-800 text-pesto-deep ${className}`}
      >
        <Music size={iconSize} aria-hidden />
      </div>
    );
  }

  return (
    <img
      src={src}
      alt={alt}
      loading="lazy"
      className={`object-cover ${className}`}
      onError={() => setFailedSrc(src)}
    />
  );
}
