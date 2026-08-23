import { useQuery } from '@tanstack/react-query'

export interface CityWeather {
  city: string
  temperature: number
  weatherCode: number
}

interface OpenMeteoResponse {
  current: {
    temperature_2m: number
    weather_code: number
  }
}

const CITIES = [
  { name: 'Sivas', latitude: 39.7477, longitude: 37.0179 },
  { name: 'İstanbul', latitude: 41.0082, longitude: 28.9784 },
  { name: 'Antalya', latitude: 36.8969, longitude: 30.7133 },
  { name: 'Ankara', latitude: 39.9334, longitude: 32.8597 },
]

async function fetchWeather(): Promise<CityWeather[]> {
  const latitude = CITIES.map((c) => c.latitude).join(',')
  const longitude = CITIES.map((c) => c.longitude).join(',')
  const url = `https://api.open-meteo.com/v1/forecast?latitude=${latitude}&longitude=${longitude}&current=temperature_2m,weather_code&timezone=auto`

  const res = await fetch(url)
  if (!res.ok) throw new Error('Hava durumu alınamadı')
  const data: OpenMeteoResponse[] = await res.json()

  return CITIES.map((city, index) => ({
    city: city.name,
    temperature: Math.round(data[index].current.temperature_2m),
    weatherCode: data[index].current.weather_code,
  }))
}

export function useWeather() {
  return useQuery({
    queryKey: ['weather', 'tr-cities'],
    queryFn: fetchWeather,
    staleTime: 15 * 60 * 1000,
    refetchInterval: 30 * 60 * 1000,
    retry: 1,
  })
}
