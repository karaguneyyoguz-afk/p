import {
  Sun,
  CloudSun,
  Cloud,
  CloudFog,
  CloudDrizzle,
  CloudRain,
  CloudSnow,
  CloudLightning,
  type LucideIcon,
} from 'lucide-react'

// WMO weather interpretation codes (https://open-meteo.com/en/docs) mapped to
// a representative icon + short Turkish label.
export function weatherIcon(code: number): LucideIcon {
  if (code === 0 || code === 1) return Sun
  if (code === 2) return CloudSun
  if (code === 3) return Cloud
  if (code === 45 || code === 48) return CloudFog
  if (code >= 51 && code <= 57) return CloudDrizzle
  if ((code >= 61 && code <= 67) || (code >= 80 && code <= 82)) return CloudRain
  if ((code >= 71 && code <= 77) || code === 85 || code === 86) return CloudSnow
  if (code >= 95) return CloudLightning
  return Cloud
}

export function weatherLabel(code: number): string {
  if (code === 0) return 'Açık'
  if (code === 1) return 'Az bulutlu'
  if (code === 2) return 'Parçalı bulutlu'
  if (code === 3) return 'Kapalı'
  if (code === 45 || code === 48) return 'Sisli'
  if (code >= 51 && code <= 57) return 'Çisenti'
  if ((code >= 61 && code <= 67) || (code >= 80 && code <= 82)) return 'Yağmurlu'
  if ((code >= 71 && code <= 77) || code === 85 || code === 86) return 'Karlı'
  if (code >= 95) return 'Gök gürültülü'
  return 'Bilinmiyor'
}
