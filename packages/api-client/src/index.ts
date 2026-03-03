/**
 * softwareos-base API Client — public exports.
 * URI: softwareos-base://packages/api-client
 */
export { EcoApiClient } from './client';
export type {
  ClientConfig, RetryConfig, RequestInterceptor,
  RequestConfig, ApiResponse, ApiError,
} from './client';
