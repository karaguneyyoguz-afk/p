import { useWeather } from '@/api/weather'
import { weatherIcon, weatherLabel } from '@/lib/weatherCodes'

// Short labels keep this compact in the Topbar; full city name shows on hover.
const CITY_SHORT: Record<string, string> = {
  Sivas: 'Sivas',
  İstanbul: 'İst.',
  Antalya: 'Antalya',
  Ankara: 'Ankara',
}

export function WeatherStrip() {
  const { data, isLoading, isError } = useWeather()

  if (isLoading || isError || !data) return null

  return (
    <div className="hidden items-center gap-3 border-r border-enigma-border pr-3 xl:flex">
      {data.map((cityWeather) => {
        const Icon = weatherIcon(cityWeather.weatherCode)
        return (
          <div
            key={cityWeather.city}
            title={`${cityWeather.city}: ${weatherLabel(cityWeather.weatherCode)}, ${cityWeather.temperature}°C`}
            className="flex items-center gap-1 text-enigma-text-muted"
          >
            <Icon className="h-4 w-4 shrink-0" />
            <span className="text-xs font-medium text-enigma-text">
              {CITY_SHORT[cityWeather.city]}
            </span>
            <span className="text-xs">{cityWeather.temperature}°</span>
          </div>
        )
      })}
    </div>
  )
}
