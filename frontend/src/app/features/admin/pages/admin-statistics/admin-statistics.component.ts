import {
  ChangeDetectionStrategy,
  Component,
  inject,
  OnInit,
  signal,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { TranslatePipe, TranslateService } from '@ngx-translate/core';
import { AdminApiService } from '../../services/admin-api.service';
import { StatsResponse } from '../../models/admin.models';

@Component({
  selector: 'app-admin-statistics',
  standalone: true,
  imports: [CommonModule, TranslatePipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './admin-statistics.component.html',
  styleUrls: ['./admin-statistics.component.scss'],
})
export class AdminStatisticsComponent implements OnInit {
  private readonly api = inject(AdminApiService);
  private readonly translate = inject(TranslateService);

  readonly stats = signal<StatsResponse | null>(null);
  readonly loading = signal(false);
  readonly tooltip = signal<{ text: string; x: number; y: number } | null>(null);

  readonly ROLE_COLORS: Record<string, string> = {
    voter: '#5b4fe8',
    organizer: '#c8f135',
    auditor: '#4d96ff',
    global_admin: '#ff6b6b',
  };

  ngOnInit(): void {
    this.loading.set(true);
    this.api.getStats().subscribe({
      next: (data) => {
        this.stats.set(data);
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
  }

  showTooltip(event: MouseEvent, text: string): void {
    this.tooltip.set({ text, x: event.clientX + 12, y: event.clientY - 8 });
  }

  moveTooltip(event: MouseEvent): void {
    const t = this.tooltip();
    if (t) this.tooltip.set({ ...t, x: event.clientX + 12, y: event.clientY - 8 });
  }

  hideTooltip(): void {
    this.tooltip.set(null);
  }

  getLineX(index: number, total: number): number {
    return (index / Math.max(total - 1, 1)) * 600;
  }

  getLineY(value: number, max: number): number {
    return 120 - (value / max) * 100 - 10;
  }

  getBarHeight(value: number, max: number): number {
    return max > 0 ? Math.round((value / max) * 100) : 0;
  }

  getBarWidth(value: number, max: number): number {
    return max > 0 ? Math.round((value / max) * 100) : 0;
  }

  maxVotingsPerDay(s: StatsResponse): number {
    return Math.max(...s.votings_per_day.map((b) => b.count), 1);
  }

  maxVotesPerDay(s: StatsResponse): number {
    return Math.max(...s.votes_per_day.map((b) => b.count), 1);
  }

  getLinePoints(data: { date: string; count: number }[]): string {
    if (!data.length) return '';
    const w = 600;
    const h = 100;
    const maxVal = Math.max(...data.map((d) => d.count), 1);
    return data
      .map((d, i) => {
        const x = (i / Math.max(data.length - 1, 1)) * w;
        const y = h - (d.count / maxVal) * h + 10;
        return `${x.toFixed(1)},${y.toFixed(1)}`;
      })
      .join(' ');
  }

  shouldShowLabel(index: number, total: number): boolean {
    if (total <= 7) return true;
    const step = total > 10 ? 3 : 2;
    return index % step === 0 || index === total - 1;
  }

  votingsTooltip(date: string, count: number): string {
    return `${date}: ${count} ${this.translate.instant('admin.statistics.tooltipVotings')}`;
  }

  votesTooltip(date: string, count: number): string {
    return `${date}: ${count} ${this.translate.instant('admin.statistics.tooltipVotes')}`;
  }

  getDonutSegments(
    data: { role: string; count: number }[],
  ): { path: string; color: string; label: string; pct: number }[] {
    const total = data.reduce((sum, d) => sum + d.count, 0);
    if (total === 0) return [];

    const cx = 80;
    const cy = 80;
    const r = 60;
    const innerR = 36;
    const segments: { path: string; color: string; label: string; pct: number }[] = [];
    let startAngle = -Math.PI / 2;

    for (let i = 0; i < data.length; i++) {
      const item = data[i];
      const fraction = item.count / total;
      if (fraction <= 0) continue;

      const angle = fraction * 2 * Math.PI;
      const endAngle = startAngle + angle;

      const pct = Math.round(fraction * 100);
      const color = this.ROLE_COLORS[item.role] ?? '#aaa';

      if (fraction >= 0.9999) {
        const path =
          `M ${cx} ${(cy - r).toFixed(2)} ` +
          `A ${r} ${r} 0 1 1 ${cx} ${(cy + r).toFixed(2)} ` +
          `A ${r} ${r} 0 1 1 ${cx} ${(cy - r).toFixed(2)} Z ` +
          `M ${cx} ${(cy - innerR).toFixed(2)} ` +
          `A ${innerR} ${innerR} 0 1 0 ${cx} ${(cy + innerR).toFixed(2)} ` +
          `A ${innerR} ${innerR} 0 1 0 ${cx} ${(cy - innerR).toFixed(2)} Z`;
        segments.push({ path, color, label: item.role, pct });
        startAngle = endAngle;
        continue;
      }

      const x1 = cx + r * Math.cos(startAngle);
      const y1 = cy + r * Math.sin(startAngle);
      const x2 = cx + r * Math.cos(endAngle);
      const y2 = cy + r * Math.sin(endAngle);
      const ix1 = cx + innerR * Math.cos(endAngle);
      const iy1 = cy + innerR * Math.sin(endAngle);
      const ix2 = cx + innerR * Math.cos(startAngle);
      const iy2 = cy + innerR * Math.sin(startAngle);
      const largeArc = angle > Math.PI ? 1 : 0;

      const path =
        `M ${x1.toFixed(2)} ${y1.toFixed(2)} ` +
        `A ${r} ${r} 0 ${largeArc} 1 ${x2.toFixed(2)} ${y2.toFixed(2)} ` +
        `L ${ix1.toFixed(2)} ${iy1.toFixed(2)} ` +
        `A ${innerR} ${innerR} 0 ${largeArc} 0 ${ix2.toFixed(2)} ${iy2.toFixed(2)} Z`;

      segments.push({ path, color, label: item.role, pct });
      startAngle = endAngle;
    }

    return segments;
  }
}
