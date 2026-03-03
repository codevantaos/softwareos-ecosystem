/**
 * softwareos-base API Client — typed HTTP client with retry + interceptors.
 * URI: softwareos-base://packages/api-client/client
 */

export interface RetryConfig {
  maxRetries: number;
  baseDelay: number;
  maxDelay: number;
  retryOn: number[];
}

export interface RequestInterceptor {
  onRequest?: (config: RequestConfig) => RequestConfig | Promise<RequestConfig>;
  onResponse?: (response: ApiResponse<unknown>) => ApiResponse<unknown>;
  onError?: (error: ApiError) => void;
}

export interface RequestConfig {
  method: string;
  path: string;
  headers: Record<string, string>;
  body?: unknown;
  params?: Record<string, string>;
}

export interface ApiResponse<T> {
  data: T;
  status: number;
  headers: Record<string, string>;
  latency_ms: number;
}

export interface ApiError {
  message: string;
  status: number;
  code: string;
  request_id?: string;
}

export interface ClientConfig {
  baseUrl: string;
  apiKey?: string;
  timeout?: number;
  retry?: Partial<RetryConfig>;
  interceptors?: RequestInterceptor[];
}

const DEFAULT_RETRY: RetryConfig = {
  maxRetries: 2,
  baseDelay: 500,
  maxDelay: 8000,
  retryOn: [502, 503, 504, 429],
};

export class EcoApiClient {
  private baseUrl: string;
  private apiKey: string;
  private timeout: number;
  private retry: RetryConfig;
  private interceptors: RequestInterceptor[];

  constructor(config: ClientConfig) {
    this.baseUrl = config.baseUrl.replace(/\/$/, '');
    this.apiKey = config.apiKey || '';
    this.timeout = config.timeout || 30000;
    this.retry = { ...DEFAULT_RETRY, ...config.retry };
    this.interceptors = config.interceptors || [];
  }

  private async request<T>(method: string, path: string, body?: unknown, params?: Record<string, string>): Promise<ApiResponse<T>> {
    let config: RequestConfig = {
      method, path,
      headers: {
        'Content-Type': 'application/json',
        ...(this.apiKey ? { 'Authorization': `Bearer ${this.apiKey}` } : {}),
      },
      body, params,
    };

    for (const i of this.interceptors) {
      if (i.onRequest) config = await i.onRequest(config);
    }

    const url = new URL(path, this.baseUrl);
    if (params) Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v));

    let lastError: Error | null = null;
    for (let attempt = 0; attempt <= this.retry.maxRetries; attempt++) {
      if (attempt > 0) {
        const delay = Math.min(this.retry.baseDelay * Math.pow(2, attempt - 1), this.retry.maxDelay);
        await new Promise(r => setTimeout(r, delay));
      }

      const start = Date.now();
      try {
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), this.timeout);

        const resp = await fetch(url.toString(), {
          method: config.method,
          headers: config.headers,
          body: config.body ? JSON.stringify(config.body) : undefined,
          signal: controller.signal,
        });
        clearTimeout(timer);

        const latency_ms = Date.now() - start;

        if (!resp.ok && this.retry.retryOn.includes(resp.status) && attempt < this.retry.maxRetries) {
          lastError = new Error(`HTTP ${resp.status}`);
          continue;
        }

        const data = await resp.json() as T;
        const respHeaders: Record<string, string> = {};
        resp.headers.forEach((v, k) => { respHeaders[k] = v; });

        const result: ApiResponse<T> = { data, status: resp.status, headers: respHeaders, latency_ms };

        for (const i of this.interceptors) {
          if (i.onResponse) i.onResponse(result as ApiResponse<unknown>);
        }

        return result;
      } catch (err) {
        lastError = err as Error;
        if (attempt >= this.retry.maxRetries) break;
      }
    }

    const apiError: ApiError = {
      message: lastError?.message || 'Request failed',
      status: 0, code: 'NETWORK_ERROR',
    };
    for (const i of this.interceptors) {
      if (i.onError) i.onError(apiError);
    }
    throw apiError;
  }

  // --- Typed API methods ---

  async health(): Promise<ApiResponse<{ status: string; version: string }>> {
    return this.request('GET', '/health');
  }

  async listModels(): Promise<ApiResponse<{ models: Array<{ id: string; name: string; status: string }> }>> {
    return this.request('GET', '/v1/models');
  }

  async chatCompletion(body: {
    model: string; messages: Array<{ role: string; content: string }>;
    max_tokens?: number; temperature?: number; stream?: boolean;
  }): Promise<ApiResponse<{ id: string; choices: Array<{ message: { content: string } }> }>> {
    return this.request('POST', '/v1/chat/completions', body);
  }

  async embed(body: {
    input: string[]; model?: string; dimensions?: number;
  }): Promise<ApiResponse<{ data: Array<{ embedding: number[] }> }>> {
    return this.request('POST', '/v1/embeddings', body);
  }

  async generateYAML(body: {
    name: string; namespace?: string; kind?: string;
  }): Promise<ApiResponse<{ content: string; valid: boolean }>> {
    return this.request('POST', '/api/v1/yaml/generate', body);
  }

  async validateYAML(body: {
    content: string; strict?: boolean;
  }): Promise<ApiResponse<{ valid: boolean; errors: Array<{ path: string; message: string }> }>> {
    return this.request('POST', '/api/v1/yaml/validate', body);
  }

  async listPlatforms(): Promise<ApiResponse<{ platforms: Array<{ id: string; name: string; type: string }> }>> {
    return this.request('GET', '/api/v1/platforms');
  }

  async getMetrics(): Promise<ApiResponse<string>> {
    return this.request('GET', '/metrics');
  }
}

export default EcoApiClient;
