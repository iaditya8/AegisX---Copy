'use client';

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReactNode, useState, useEffect } from 'react';

export default function Providers({ children }: { children: ReactNode }) {
  const [mswReady, setMswReady] = useState(false);

  useEffect(() => {
    async function initMsw() {
      if (process.env.NODE_ENV === 'development' && process.env.NEXT_PUBLIC_DISABLE_MSW !== 'true') {
        try {
          const { worker } = await import('../test/msw/browser');
          await worker.start({
            onUnhandledRequest: 'bypass',
          });
        } catch (error) {
          console.error('Failed to start MSW worker:', error);
        }
      }
      setMswReady(true);
    }
    initMsw();
  }, []);

  // Use state to instantiate query client once per session
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 60000,
            refetchOnWindowFocus: false,
            retry: false,
          },
        },
      })
  );

  if (!mswReady) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-zinc-950 text-zinc-400">
        <div className="text-lg">Initializing AegisX Demo Mode...</div>
      </div>
    );
  }

  return (
    <QueryClientProvider client={queryClient}>
      {children}
    </QueryClientProvider>
  );
}
