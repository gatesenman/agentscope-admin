export interface BackendStatus {
  mode?: string
  redis?: boolean
  banner?: string
  banner_zh?: string
}

export function bannerText(status: BackendStatus | null, lang: 'zh' | 'en' = 'zh'): string | null {
  if (!status) return null
  if (status.mode === 'demo' || status.redis === false) {
    if (lang === 'zh') return status.banner_zh || status.banner || '演示模式：后端未连接。'
    return status.banner || 'Demo mode: the real backend is not connected.'
  }
  return null
}
