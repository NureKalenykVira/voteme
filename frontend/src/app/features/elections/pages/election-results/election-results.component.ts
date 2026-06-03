import {
  ChangeDetectionStrategy,
  Component,
  inject,
  OnDestroy,
  OnInit,
  signal,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router } from '@angular/router';
import { TranslatePipe, TranslateService } from '@ngx-translate/core';
import { PublicHeaderComponent } from '../../../../shared/layout/public-header/public-header.component';
import { PublicFooterComponent } from '../../../../shared/layout/public-footer/public-footer.component';
import { ElectionsApiService } from '../../services/elections-api.service';
import {
  ElectionResultsResponse,
  OptionResultResponse,
  TimelineBucket,
  TimelineResponse,
  VoterReceiptResponse,
} from '../../models/elections.models';
import { environment } from '../../../../../environments/environment';
import { AuthStorageService } from '../../../../core/services/auth-storage.service';
import { ToastService } from '../../../../shared/ui/toast/toast.service';

@Component({
  selector: 'app-election-results',
  standalone: true,
  imports: [CommonModule, PublicHeaderComponent, PublicFooterComponent, TranslatePipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './election-results.component.html',
  styleUrls: ['./election-results.component.scss'],
})
export class ElectionResultsComponent implements OnInit, OnDestroy {
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly electionsApi = inject(ElectionsApiService);
  readonly authStorage = inject(AuthStorageService);
  private readonly toast = inject(ToastService);
  private readonly translate = inject(TranslateService);

  readonly results = signal<ElectionResultsResponse | null>(null);
  readonly timeline = signal<TimelineResponse | null>(null);
  readonly notFound = signal(false);
  readonly copiedHash = signal(false);
  readonly expandedOptions = signal(new Set<string>());
  readonly hoveredPieSlice = signal<{
    path: string;
    color: string;
    title: string;
    votes: number;
  } | null>(null);

  readonly receipt = signal<VoterReceiptResponse | null>(null);
  readonly verifyState = signal<'idle' | 'loading' | 'done' | 'error'>('idle');
  readonly verifyError = signal<string>('');
  readonly hasVoted = signal(false);
  readonly copiedReceiptHash = signal(false);

  private copyTimeout?: ReturnType<typeof setTimeout>;
  private copyReceiptTimeout?: ReturnType<typeof setTimeout>;

  ngOnInit(): void {
    const id = this.route.snapshot.paramMap.get('id') ?? '';
    this.electionsApi.getResults(id).subscribe({
      next: (data) => {
        this.results.set(data);
        if (data.is_organizer) {
          this.electionsApi.getTimeline(id).subscribe({
            next: (t) => this.timeline.set(t),
            error: () => {},
          });
        }
        if (this.authStorage.isAuthenticated()) {
          this.electionsApi.getMyVote(id).subscribe({
            next: (v) => this.hasVoted.set(v.has_voted),
            error: () => {},
          });
        }
      },
      error: () => this.router.navigate(['/404']),
    });
  }

  ngOnDestroy(): void {
    clearTimeout(this.copyTimeout);
    clearTimeout(this.copyReceiptTimeout);
  }

  truncateHash(hash: string): string {
    if (hash.length <= 20) return hash;
    return hash.slice(0, 10) + '...' + hash.slice(-6);
  }

  copyHash(hash: string): void {
    navigator.clipboard.writeText(hash).then(() => {
      this.copiedHash.set(true);
      this.copyTimeout = setTimeout(() => this.copiedHash.set(false), 2000);
      this.toast.info(this.translate.instant('electionResults.toastCopied'));
    });
  }

  copyReceiptHash(hash: string): void {
    navigator.clipboard.writeText(hash).then(() => {
      this.copiedReceiptHash.set(true);
      this.copyReceiptTimeout = setTimeout(() => this.copiedReceiptHash.set(false), 2000);
      this.toast.info(this.translate.instant('electionResults.toastCopied'));
    });
  }

  verifyMyVote(): void {
    const id = this.route.snapshot.paramMap.get('id')!;
    this.verifyState.set('loading');
    this.electionsApi.getReceipt(id).subscribe({
      next: (r) => {
        this.receipt.set(r);
        this.verifyState.set('done');
      },
      error: (e: { status: number; error?: { detail?: string } }) => {
        this.verifyState.set('error');
        if (e.status === 409) {
          this.verifyError.set(this.translate.instant('electionResults.errorNotFinalized'));
        } else if (e.status === 404) {
          this.verifyError.set(this.translate.instant('electionResults.errorNoVote'));
        } else {
          this.verifyError.set(this.translate.instant('electionResults.errorVerifyFailed'));
        }
        this.toast.error(e?.error?.detail ?? this.translate.instant('electionResults.toastVerifyFailed'));
      },
    });
  }

  downloadReceipt(): void {
    const r = this.receipt();
    if (!r) return;
    const blob = new Blob([JSON.stringify(r, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `vote-receipt-${r.voting_id}.json`;
    a.click();
    URL.revokeObjectURL(url);
    this.toast.success(this.translate.instant('electionResults.toastReceiptDownloaded'));
  }

  photoUrl(url: string | undefined): string | null {
    if (!url) return null;
    return url.startsWith('/') ? `${environment.apiUrl}${url}` : url;
  }

  private denseRank(option: OptionResultResponse, options: OptionResultResponse[]): number {
    const unique = [...new Set(options.map((o) => o.votes_count))].sort((a, b) => b - a);
    return unique.indexOf(option.votes_count);
  }

  cardClass(option: OptionResultResponse, options: OptionResultResponse[]): string {
    const rank = this.denseRank(option, options);
    if (rank === 0) return 'result-card--winner';
    if (rank === 1) return 'result-card--second';
    if (rank === 2) return 'result-card--third';
    return 'result-card--participant';
  }

  isExpanded(optionId: string): boolean {
    return this.expandedOptions().has(optionId);
  }

  toggleExpand(optionId: string): void {
    const current = new Set(this.expandedOptions());
    if (current.has(optionId)) {
      current.delete(optionId);
    } else {
      current.add(optionId);
    }
    this.expandedOptions.set(current);
  }

  badgeLabel(option: OptionResultResponse, options: OptionResultResponse[]): string {
    const rank = this.denseRank(option, options);
    if (rank === 0) return 'electionResults.badgeWinner';
    if (rank === 1) return 'electionResults.badgeSecond';
    if (rank === 2) return 'electionResults.badgeThird';
    return 'electionResults.badgeParticipant';
  }

  getStatusKey(status: string): string {
    const map: Record<string, string> = {
      active: 'electionResults.statusActive',
      published: 'electionResults.statusPublished',
      draft: 'electionResults.statusDraft',
      finished: 'electionResults.statusFinished',
      archived: 'electionResults.statusArchived',
      concluded: 'electionResults.statusFinished',
    };
    return map[status] ?? status.toUpperCase();
  }

  timelineBarHeight(bucket: TimelineBucket, buckets: TimelineBucket[]): number {
    const max = Math.max(...buckets.map((b) => b.votes), 1);
    return Math.round((bucket.votes / max) * 100);
  }

  exportResults(): void {
    const data = this.results();
    if (!data) return;
    const html = this.buildReportHtml(data);
    const win = window.open('', '_blank');
    if (!win) return;
    win.document.write(html);
    win.document.close();
    win.focus();
    setTimeout(() => {
      win.print();
    }, 400);
    this.toast.info(this.translate.instant('electionResults.toastReportOpened'));
  }

  private buildReportHtml(data: ElectionResultsResponse): string {
    const fmt = (iso: string | undefined) =>
      iso
        ? new Date(iso).toLocaleDateString('en-GB', {
            day: 'numeric',
            month: 'long',
            year: 'numeric',
          })
        : '—';

    const duration = (): string => {
      if (!data.start_date_time || !data.end_date_time) return '';
      const ms = new Date(data.end_date_time).getTime() - new Date(data.start_date_time).getTime();
      const mins = Math.round(ms / 60000);
      if (mins < 60) return `${mins} min`;
      const hrs = Math.round(ms / 3600000);
      if (hrs < 48) return `${hrs} h`;
      return `${Math.round(hrs / 24)} days`;
    };

    const sortedOptions = [...data.options].sort((a, b) => b.votes_count - a.votes_count);
    const uniqueCounts = [...new Set(sortedOptions.map((o) => o.votes_count))].sort(
      (a, b) => b - a,
    );
    const maxVotes = uniqueCounts[0] ?? 0;

    const rankLabel = (votes: number): string => {
      const rank = uniqueCounts.indexOf(votes);
      if (rank === 0) return maxVotes === 0 ? 'Participant' : 'Winner 🎉';
      if (rank === 1) return '2nd place';
      if (rank === 2) return '3rd place';
      return 'Participant';
    };

    const optionsHtml = sortedOptions
      .map(
        (o) => `
      <div class="option ${uniqueCounts.indexOf(o.votes_count) === 0 && maxVotes > 0 ? 'option--winner' : ''}">
        <div class="option-header">
          <span class="option-rank">${rankLabel(o.votes_count)}</span>
          <span class="option-title">${o.title}</span>
          <span class="option-votes">${o.votes_count} votes</span>
        </div>
        ${o.description ? `<p class="option-desc">${o.description}</p>` : ''}
        <div class="bar-track">
          <div class="bar-fill" style="width: ${o.percentage}%"></div>
        </div>
        <div class="bar-meta">
          <span>${o.percentage.toFixed(1)}% of all votes</span>
        </div>
      </div>
    `,
      )
      .join('');

    const winnerOption = maxVotes > 0 ? sortedOptions[0] : null;
    const conclusionHtml = winnerOption
      ? `<div class="conclusion">
          <h3>Conclusion</h3>
          <p>The winner is <strong>${winnerOption.title}</strong> with <strong>${winnerOption.votes_count} votes</strong> (${winnerOption.percentage.toFixed(1)}%).</p>
          <p>Participation: <strong>${data.already_voted}</strong> out of <strong>${data.voters_invited}</strong> invited voters cast a ballot (<strong>${data.participation_pct.toFixed(0)}%</strong> turnout).</p>
        </div>`
      : `<div class="conclusion"><h3>Conclusion</h3><p>No votes were cast in this election.</p></div>`;

    const blockchainHtml = data.finalize_tx_hash
      ? `<div class="blockchain">
          <h3>Blockchain Verification</h3>
          <p>Results recorded on Ethereum Sepolia.</p>
          <p class="tx-hash">Transaction: <code>${data.finalize_tx_hash}</code></p>
        </div>`
      : `<div class="blockchain"><h3>Blockchain Verification</h3><p>Blockchain recording pending.</p></div>`;

    return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>${data.title} — Election Report</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: 'Segoe UI', Arial, sans-serif; font-size: 14px; color: #1a1a1a; background: #fff; padding: 20px 32px; max-width: 820px; margin: 0 auto; }

    /* Header */
    .report-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; padding-bottom: 10px; border-bottom: 3px solid #5b4fe8; }
    .report-brand { font-size: 20px; font-weight: 900; color: #5b4fe8; letter-spacing: 0.06em; }
    .report-date { font-size: 12px; color: #666; }

    /* Title */
    .report-title { font-size: 22px; font-weight: 900; color: #1a1a1a; margin-bottom: 6px; }
    .report-status { display: inline-block; font-size: 12px; font-weight: 700; letter-spacing: 0.07em; text-transform: uppercase; color: #5b4fe8; border: 2px solid #5b4fe8; border-radius: 20px; padding: 3px 12px; margin-bottom: 10px; }
    .report-meta { margin: 8px 0 10px; display: flex; flex-direction: column; gap: 4px; }
    .meta-row { display: flex; gap: 12px; font-size: 13px; }
    .meta-key { font-weight: 700; color: #888; width: 80px; flex: 0 0 auto; }
    .meta-val { font-weight: 600; color: #1a1a1a; }

    /* Stats row */
    .stats { display: flex; gap: 0; margin-bottom: 14px; border: 2px solid #e8e8e8; border-radius: 12px; overflow: hidden; }
    .stat { flex: 1; padding: 10px 16px; border-right: 1px solid #e8e8e8; }
    .stat:last-child { border-right: none; }
    .stat-num { font-size: 22px; font-weight: 900; color: #5b4fe8; line-height: 1; margin-bottom: 4px; }
    .stat-label { font-size: 12px; font-weight: 600; color: #666; text-transform: uppercase; letter-spacing: 0.05em; }

    /* Section titles */
    h2 { font-size: 16px; font-weight: 800; text-transform: uppercase; letter-spacing: 0.08em; color: #5b4fe8; margin: 10px 0 8px; }
    h3 { font-size: 14px; font-weight: 800; color: #1a1a1a; margin-bottom: 8px; }

    /* Options */
    .option { margin-bottom: 8px; padding: 8px 12px; border-radius: 10px; border: 1.5px solid #e8e8e8; }
    .option--winner { border-color: #c8f135; background: #f9ffe0; }
    .option-header { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; }
    .option-rank { font-size: 11px; font-weight: 700; background: #5b4fe8; color: #fff; border-radius: 20px; padding: 2px 10px; white-space: nowrap; }
    .option--winner .option-rank { background: #1a1a1a; }
    .option-title { font-size: 15px; font-weight: 800; flex: 1; }
    .option-votes { font-size: 13px; font-weight: 700; color: #5b4fe8; white-space: nowrap; }
    .option-desc { font-size: 12px; color: #555; margin-bottom: 8px; line-height: 1.5; }
    .bar-track { height: 10px; background: #eee; border-radius: 5px; overflow: hidden; margin-bottom: 4px; }
    .bar-fill { height: 100%; background: #5b4fe8; border-radius: 5px; }
    .option--winner .bar-fill { background: #1a1a1a; }
    .bar-meta { font-size: 11px; color: #888; font-weight: 600; }

    /* Conclusion */
    .conclusion { background: #5b4fe8; color: #fff; border-radius: 12px; padding: 12px 18px; margin-top: 12px; }
    .conclusion h3 { color: #c8f135; margin-bottom: 10px; font-size: 15px; }
    .conclusion p { margin-bottom: 6px; line-height: 1.6; }
    .conclusion strong { color: #c8f135; }

    /* Blockchain */
    .blockchain { margin-top: 10px; padding: 10px 14px; border: 2px solid #c8f135; border-radius: 10px; background: #f9ffe0; }
    .blockchain h3 { color: #1a1a1a; }
    .blockchain p { font-size: 12px; color: #555; margin-top: 4px; }
    .tx-hash code { font-family: 'Courier New', monospace; font-size: 11px; word-break: break-all; color: #5b4fe8; }

    /* Footer */
    .report-footer { margin-top: 14px; padding-top: 8px; border-top: 1px solid #e8e8e8; font-size: 11px; color: #aaa; text-align: center; break-inside: avoid; page-break-inside: avoid; }

    @media print {
      body { padding: 6px 12px; }
      @page { margin: 5mm; }
      .report-footer { break-before: avoid; page-break-before: avoid; margin-top: 16px; }
      .blockchain { break-inside: avoid; page-break-inside: avoid; }
      .conclusion { break-inside: avoid; page-break-inside: avoid; }
    }
  </style>
</head>
<body>
  <div class="report-header">
    <div class="report-brand">VoteMe</div>
    <div class="report-date">Generated: ${new Date().toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' })}</div>
  </div>

  <h1 class="report-title">${data.title}</h1>
  <span class="report-status">${data.status}</span>

  <div class="report-meta">
    ${data.organizer_name ? `<div class="meta-row"><span class="meta-key">Organizer</span><span class="meta-val">${data.organizer_name}</span></div>` : ''}
    ${data.start_date_time ? `<div class="meta-row"><span class="meta-key">Started</span><span class="meta-val">${fmt(data.start_date_time)}</span></div>` : ''}
    ${data.end_date_time ? `<div class="meta-row"><span class="meta-key">Ended</span><span class="meta-val">${fmt(data.end_date_time)}</span></div>` : ''}
    ${data.start_date_time && data.end_date_time ? `<div class="meta-row"><span class="meta-key">Duration</span><span class="meta-val">${duration()}</span></div>` : ''}
  </div>

  <div class="stats">
    <div class="stat">
      <div class="stat-num">${data.voters_invited}</div>
      <div class="stat-label">Invited</div>
    </div>
    <div class="stat">
      <div class="stat-num">${data.already_voted}</div>
      <div class="stat-label">Voted</div>
    </div>
    <div class="stat">
      <div class="stat-num">${data.participation_pct.toFixed(0)}%</div>
      <div class="stat-label">Turnout</div>
    </div>
    <div class="stat">
      <div class="stat-num">${data.options.length}</div>
      <div class="stat-label">Options</div>
    </div>
  </div>

  <h2>Vote Distribution</h2>
  ${optionsHtml}

  ${conclusionHtml}
  ${blockchainHtml}

  <div class="report-footer">VoteMe — Transparent Electronic Voting · Election ID: ${data.voting_id}</div>
</body>
</html>`;
  }

  goBack(): void {
    this.router.navigate(['/my-votings']);
  }

  readonly PIE_COLORS = [
    '#5b4fe8',
    '#c8f135',
    '#ff6b6b',
    '#ffd93d',
    '#6bcb77',
    '#4d96ff',
    '#ff9f43',
    '#a29bfe',
  ];

  showPieTooltip(slice: { path: string; color: string; title: string; votes: number }): void {
    this.hoveredPieSlice.set(slice);
  }

  hidePieTooltip(): void {
    this.hoveredPieSlice.set(null);
  }

  getPieSlices(
    options: OptionResultResponse[],
  ): Array<{ path: string; color: string; title: string; votes: number }> {
    const total = options.reduce((sum, o) => sum + o.votes_count, 0);
    const cx = 80,
      cy = 80,
      r = 72;
    const slices: Array<{ path: string; color: string; title: string; votes: number }> = [];

    if (total === 0) {
      const angle = (2 * Math.PI) / options.length;
      let startAngle = -Math.PI / 2;
      for (let i = 0; i < options.length; i++) {
        const endAngle = startAngle + angle;
        const x1 = cx + r * Math.cos(startAngle);
        const y1 = cy + r * Math.sin(startAngle);
        const x2 = cx + r * Math.cos(endAngle);
        const y2 = cy + r * Math.sin(endAngle);
        slices.push({
          path: `M ${cx} ${cy} L ${x1.toFixed(2)} ${y1.toFixed(2)} A ${r} ${r} 0 0 1 ${x2.toFixed(2)} ${y2.toFixed(2)} Z`,
          color: this.PIE_COLORS[i % this.PIE_COLORS.length],
          title: options[i].title,
          votes: 0,
        });
        startAngle = endAngle;
      }
      return slices;
    }

    let startAngle = -Math.PI / 2;
    for (let i = 0; i < options.length; i++) {
      const fraction = options[i].votes_count / total;
      const color = this.PIE_COLORS[i % this.PIE_COLORS.length];

      if (fraction <= 0) {
        slices.push({ path: '', color, title: options[i].title, votes: options[i].votes_count });
        continue;
      }

      if (fraction >= 0.9999) {
        // Full circle: draw as two semicircles
        const path = `M ${cx} ${(cy - r).toFixed(2)} A ${r} ${r} 0 1 1 ${cx} ${(cy + r).toFixed(2)} A ${r} ${r} 0 1 1 ${cx} ${(cy - r).toFixed(2)} Z`;
        slices.push({ path, color, title: options[i].title, votes: options[i].votes_count });
        continue;
      }

      const angle = fraction * 2 * Math.PI;
      const endAngle = startAngle + angle;
      const x1 = cx + r * Math.cos(startAngle);
      const y1 = cy + r * Math.sin(startAngle);
      const x2 = cx + r * Math.cos(endAngle);
      const y2 = cy + r * Math.sin(endAngle);
      const largeArc = angle > Math.PI ? 1 : 0;
      slices.push({
        path: `M ${cx} ${cy} L ${x1.toFixed(2)} ${y1.toFixed(2)} A ${r} ${r} 0 ${largeArc} 1 ${x2.toFixed(2)} ${y2.toFixed(2)} Z`,
        color,
        title: options[i].title,
        votes: options[i].votes_count,
      });
      startAngle = endAngle;
    }
    return slices;
  }
}
