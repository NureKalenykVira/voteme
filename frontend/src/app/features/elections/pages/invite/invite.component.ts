import { ChangeDetectionStrategy, Component, inject, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router } from '@angular/router';
import { QRCodeComponent } from 'angularx-qrcode';
import { TranslatePipe, TranslateService } from '@ngx-translate/core';
import { ElectionsApiService } from '../../services/elections-api.service';
import { CsvImportResult } from '../../models/elections.models';
import { ToastService } from '../../../../shared/ui/toast/toast.service';

@Component({
  selector: 'app-invite',
  standalone: true,
  imports: [CommonModule, QRCodeComponent, TranslatePipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './invite.component.html',
  styleUrls: ['./invite.component.scss'],
})
export class InviteComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly electionsApi = inject(ElectionsApiService);
  private readonly toast = inject(ToastService);
  private readonly translate = inject(TranslateService);

  readonly electionId = this.route.snapshot.paramMap.get('id') ?? '';
  readonly inviteCode = signal<string>('');
  readonly inviteLink = signal<string>('');
  readonly copiedCode = signal(false);
  readonly copiedLink = signal(false);
  readonly csvFile = signal<File | null>(null);
  readonly isDragOver = signal(false);

  readonly csvImportLoading = signal(false);
  readonly csvImportResult = signal<CsvImportResult | null>(null);
  readonly csvImportError = signal('');

  ngOnInit(): void {
    if (this.electionId) {
      this.electionsApi.getById(this.electionId).subscribe({
        next: (election) => {
          const code = election.invitation_code ?? '';
          this.inviteCode.set(code);
          this.inviteLink.set(`${window.location.origin}/join/${code}`);
        },
      });
    }
  }

  copyCode(): void {
    navigator.clipboard.writeText(this.inviteCode()).then(() => {
      this.copiedCode.set(true);
      setTimeout(() => this.copiedCode.set(false), 2000);
      this.toast.info(this.translate.instant('invite.toastCopied'));
    });
  }

  copyLink(): void {
    navigator.clipboard.writeText(this.inviteLink()).then(() => {
      this.copiedLink.set(true);
      setTimeout(() => this.copiedLink.set(false), 2000);
      this.toast.info(this.translate.instant('invite.toastCopied'));
    });
  }

  downloadQr(): void {
    const canvas = document.querySelector('qrcode canvas') as HTMLCanvasElement;
    if (!canvas) return;
    const link = document.createElement('a');
    link.download = `vote-qr-${this.electionId}.png`;
    link.href = canvas.toDataURL('image/png');
    link.click();
    this.toast.info(this.translate.instant('invite.toastQrDownloaded'));
  }

  onFileSelected(event: Event): void {
    const file = (event.target as HTMLInputElement).files?.[0];
    if (file) {
      this.csvFile.set(file);
      this.csvImportResult.set(null);
      this.csvImportError.set('');
    }
  }

  onDragOver(event: DragEvent): void {
    event.preventDefault();
    this.isDragOver.set(true);
  }

  onDragLeave(): void {
    this.isDragOver.set(false);
  }

  onDrop(event: DragEvent): void {
    event.preventDefault();
    this.isDragOver.set(false);
    const file = event.dataTransfer?.files?.[0];
    if (file) {
      this.csvFile.set(file);
      this.csvImportResult.set(null);
      this.csvImportError.set('');
    }
  }

  resetImport(): void {
    this.csvImportResult.set(null);
    this.csvImportError.set('');
  }

  uploadCsv(): void {
    const file = this.csvFile();
    if (!file || !this.electionId || this.csvImportLoading()) return;
    this.csvImportLoading.set(true);
    this.csvImportError.set('');
    this.csvImportResult.set(null);
    this.electionsApi.importVotersCsv(this.electionId, file).subscribe({
      next: (result) => {
        this.csvImportResult.set(result);
        this.csvImportLoading.set(false);
        this.csvFile.set(null);
        this.toast.success(this.translate.instant('invite.toastImported'));
      },
      error: (err) => {
        this.csvImportError.set(err?.error?.detail ?? this.translate.instant('invite.toastImportFailed'));
        this.csvImportLoading.set(false);
      },
    });
  }

  manageVoters(): void {
    this.router.navigate([`/elections/${this.electionId}/voters`]);
  }

  done(): void {
    this.router.navigate(['/my-votings']);
  }
}
