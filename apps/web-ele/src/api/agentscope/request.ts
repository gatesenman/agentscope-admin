/**
 * Dedicated request client for the AgentScope backend.
 *
 * Unlike the demo `requestClient`, the AgentScope backend returns raw JSON
 * bodies (no `{ code, data }` envelope), so we use `responseReturn: 'body'`.
 * Identity is currently passed via the `X-User-ID` header (the backend's
 * placeholder auth); this will be replaced by JWT once the backend adds it.
 */
import { useAppConfig } from '@vben/hooks';
import { preferences } from '@vben/preferences';
import {
  defaultResponseInterceptor,
  errorMessageResponseInterceptor,
  RequestClient,
} from '@vben/request';

import { ElMessage } from 'element-plus';

const { apiURL } = useAppConfig(import.meta.env, import.meta.env.PROD);

/** The current AgentScope user id (single-tenant admin for now). */
export function getAgentScopeUserId(): string {
  return localStorage.getItem('agentscope-user-id') || 'admin';
}

const client = new RequestClient({
  baseURL: apiURL,
  responseReturn: 'body',
});

client.addRequestInterceptor({
  fulfilled: (config) => {
    config.headers['X-User-ID'] = getAgentScopeUserId();
    config.headers['Accept-Language'] = preferences.app.locale;
    return config;
  },
});

client.addResponseInterceptor(
  defaultResponseInterceptor({
    codeField: 'code',
    dataField: 'data',
    successCode: 0,
  }),
);

client.addResponseInterceptor(
  errorMessageResponseInterceptor((msg: string, error) => {
    const responseData = error?.response?.data ?? {};
    const errorMessage = responseData?.detail ?? responseData?.message ?? '';
    ElMessage.error(
      typeof errorMessage === 'string' && errorMessage ? errorMessage : msg,
    );
  }),
);

export const agentScopeClient = client;
