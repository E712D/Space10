import 'leaflet/dist/leaflet.css';
import { CircleMarker, MapContainer, Popup, TileLayer, useMap } from 'react-leaflet';
import { useEffect } from 'react';
import { cn } from '../lib/cn';
import type { PlotOut } from '../types/api';

type MapPlot = Pick<PlotOut, 'plot_id' | 'name' | 'latitude' | 'longitude'>;

interface FarmMapProps {
  plots: MapPlot[];
  activeId?: string;
  onSelect?: (plotId: string) => void;
  label: string;
  className?: string;
}

function MapView({ plot }: { plot: MapPlot }) {
  const map = useMap();
  useEffect(() => {
    map.setView([plot.latitude, plot.longitude], map.getZoom(), { animate: false });
  }, [map, plot.latitude, plot.longitude]);
  return null;
}

/** Carte OpenStreetMap centrée sur les coordonnées réelles des parcelles. */
export function FarmMap({ plots, activeId, onSelect, label, className }: FarmMapProps) {
  const active = plots.find((plot) => plot.plot_id === activeId) ?? plots[0];
  if (!active) return null;

  return (
    <div className={cn('h-56 w-full overflow-hidden', className)} role="img" aria-label={label}>
      <MapContainer center={[active.latitude, active.longitude]} zoom={13} scrollWheelZoom={false} className="z-0 h-full w-full">
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <MapView plot={active} />
        {plots.map((plot) => {
          const selected = plot.plot_id === activeId;
          return (
            <CircleMarker
              key={plot.plot_id}
              center={[plot.latitude, plot.longitude]}
              radius={selected ? 11 : 8}
              pathOptions={{
                color: selected ? '#1f4d36' : '#2f5d46',
                fillColor: selected ? '#77b58a' : '#b4d9bd',
                fillOpacity: 0.9,
                weight: selected ? 3 : 2,
              }}
              eventHandlers={onSelect ? { click: () => onSelect(plot.plot_id) } : undefined}
            >
              <Popup>{plot.name}</Popup>
            </CircleMarker>
          );
        })}
      </MapContainer>
    </div>
  );
}
