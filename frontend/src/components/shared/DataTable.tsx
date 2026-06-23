import React from 'react';
import { ArrowUpDown, ChevronLeft, ChevronRight } from 'lucide-react';
import { LoadingState } from './LoadingState';

export interface Column<T> {
  key: string;
  label: string;
  sortable?: boolean;
  render?: (row: T) => React.ReactNode;
}

interface DataTableProps<T> {
  columns: Column<T>[];
  data: T[];
  isLoading?: boolean;
  emptyMessage?: string;
  // Sorting props
  sortBy?: string;
  sortOrder?: 'asc' | 'desc';
  onSort?: (key: string) => void;
  // Pagination props
  currentPage?: number;
  totalPages?: number;
  onPageChange?: (page: number) => void;
}

export function DataTable<T extends { id: string | number }>({
  columns,
  data,
  isLoading,
  emptyMessage = 'No data available',
  sortBy,
  sortOrder,
  onSort,
  currentPage,
  totalPages,
  onPageChange,
}: DataTableProps<T>) {
  return (
    <div className="w-full flex flex-col rounded-xl border border-zinc-900 bg-zinc-950/40 backdrop-blur-md overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse text-sm text-zinc-300">
          <thead>
            <tr className="border-b border-zinc-900 bg-zinc-900/20">
              {columns.map((col) => (
                <th
                  key={col.key}
                  className={`p-4 font-semibold text-zinc-400 select-none ${
                    col.sortable && onSort ? 'cursor-pointer hover:text-white' : ''
                  }`}
                  onClick={() => col.sortable && onSort && onSort(col.key)}
                >
                  <div className="flex items-center gap-1.5">
                    {col.label}
                    {col.sortable && onSort && (
                      <ArrowUpDown
                        className={`h-3.5 w-3.5 transition-colors ${
                          sortBy === col.key ? 'text-indigo-400' : 'text-zinc-600'
                        }`}
                      />
                    )}
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td colSpan={columns.length} className="p-8 text-center">
                  <div className="flex justify-center items-center">
                    <LoadingState message="Loading data table..." />
                  </div>
                </td>
              </tr>
            ) : data.length === 0 ? (
              <tr>
                <td colSpan={columns.length} className="p-12 text-center text-zinc-500 font-medium">
                  {emptyMessage}
                </td>
              </tr>
            ) : (
              data.map((row, idx) => (
                <tr
                  key={row.id || idx}
                  className="border-b border-zinc-900/60 hover:bg-zinc-900/30 transition-colors duration-150"
                >
                  {columns.map((col) => (
                    <td key={col.key} className="p-4 align-middle">
                      {col.render ? col.render(row) : (row as any)[col.key] ?? '-'}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination Bar */}
      {currentPage !== undefined && totalPages !== undefined && onPageChange && totalPages > 1 && (
        <div className="flex items-center justify-between p-4 border-t border-zinc-900 bg-zinc-900/10">
          <div className="text-xs text-zinc-500 font-mono">
            Page {currentPage} of {totalPages}
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => onPageChange(currentPage - 1)}
              disabled={currentPage <= 1}
              className="flex items-center justify-center h-8 w-8 rounded-lg border border-zinc-800 bg-zinc-950 hover:bg-zinc-900 disabled:opacity-40 disabled:hover:bg-zinc-950 text-zinc-400 hover:text-white transition-all duration-150"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <button
              onClick={() => onPageChange(currentPage + 1)}
              disabled={currentPage >= totalPages}
              className="flex items-center justify-center h-8 w-8 rounded-lg border border-zinc-800 bg-zinc-950 hover:bg-zinc-900 disabled:opacity-40 disabled:hover:bg-zinc-950 text-zinc-400 hover:text-white transition-all duration-150"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
