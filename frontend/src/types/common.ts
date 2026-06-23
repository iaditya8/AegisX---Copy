export interface StandardResponse<T> {
  success: boolean;
  data: T;
  meta?: {
    total?: number;
    page?: number;
    page_size?: number;
    [key: string]: any;
  };
  trace_id?: string;
}
