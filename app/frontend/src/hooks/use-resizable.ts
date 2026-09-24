import { useCallback, useEffect, useRef, useState } from 'react';

interface UseResizableOptions {
  minWidth?: number;
  maxWidth?: number;
  defaultWidth?: number;
}

export function useResizable({
  minWidth = 200,
  maxWidth = 500,
  defaultWidth = 250
}: UseResizableOptions = {}) {
  const [width, setWidth] = useState(defaultWidth);
  const [isDragging, setIsDragging] = useState(false);
  const elementRef = useRef<HTMLDivElement>(null);

  const startResize = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  // Listeners are owned by the effect so the cleanup removes the exact
  // function identities that were added.
  useEffect(() => {
    if (!isDragging) return;

    const handleMouseMove = (e: MouseEvent) => {
      const elementLeft = elementRef.current?.getBoundingClientRect().left || 0;
      setWidth(Math.max(minWidth, Math.min(maxWidth, e.clientX - elementLeft)));
    };

    const stopResize = () => setIsDragging(false);

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', stopResize);

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', stopResize);
    };
  }, [isDragging, minWidth, maxWidth]);

  return {
    width,
    isDragging,
    elementRef,
    startResize
  };
}
