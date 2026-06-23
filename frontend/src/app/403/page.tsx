import Link from 'next/link';
import { ShieldAlert } from 'lucide-react';

export default function AccessDenied() {
  return (
    <main className="flex h-screen w-screen flex-col items-center justify-center bg-zinc-950 px-4 text-center text-zinc-200">
      <div className="max-w-md space-y-6">
        <div className="flex justify-center">
          <div className="rounded-full bg-red-950/30 p-4 border border-red-500/20">
            <ShieldAlert className="h-12 w-12 text-red-500" />
          </div>
        </div>
        
        <h1 className="text-3xl font-extrabold tracking-tight text-white sm:text-4xl">
          403 - Access Denied
        </h1>
        
        <p className="text-sm text-zinc-400">
          Your account role does not have the required permissions to access this page. Please contact your system administrator.
        </p>

        <div className="flex justify-center pt-2">
          <Link
            href="/"
            className="rounded bg-indigo-600 px-4 py-2 text-sm font-semibold text-white transition-colors duration-200 hover:bg-indigo-500 shadow-lg shadow-indigo-600/20"
          >
            Return to Dashboard
          </Link>
        </div>
      </div>
    </main>
  );
}
