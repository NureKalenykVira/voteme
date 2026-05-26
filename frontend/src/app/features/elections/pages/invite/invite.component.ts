import { ChangeDetectionStrategy, Component, inject, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router } from '@angular/router';
import { QRCodeComponent } from 'angularx-qrcode';
import { ElectionsApiService } from '../../services/elections-api.service';

@Component({
  selector: 'app-invite',
  standalone: true,
  imports: [CommonModule, QRCodeComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './invite.component.html',
  styleUrls: ['./invite.component.scss'],
})
export class InviteComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly electionsApi = inject(ElectionsApiService);

  readonly electionId = this.route.snapshot.paramMap.get('id') ?? '';
  readonly inviteCode = signal<string>('');
  readonly inviteLink = signal<string>('');
  readonly copiedCode = signal(false);
  readonly copiedLink = signal(false);
  readonly csvFile = signal<File | null>(null);
  readonly isDragOver = signal(false);

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
    });
  }

  copyLink(): void {
    navigator.clipboard.writeText(this.inviteLink()).then(() => {
      this.copiedLink.set(true);
      setTimeout(() => this.copiedLink.set(false), 2000);
    });
  }

  downloadQr(): void {
    const canvas = document.querySelector('qrcode canvas') as HTMLCanvasElement;
    if (!canvas) return;
    const link = document.createElement('a');
    link.download = `vote-qr-${this.electionId}.png`;
    link.href = canvas.toDataURL('image/png');
    link.click();
  }

  onFileSelected(event: Event): void {
    const file = (event.target as HTMLInputElement).files?.[0];
    if (file) this.csvFile.set(file);
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
    if (file) this.csvFile.set(file);
  }

  manageVoters(): void {
    this.router.navigate([`/elections/${this.electionId}/voters`]);
  }

  done(): void {
    this.router.navigate(['/my-votings']);
  }
}
