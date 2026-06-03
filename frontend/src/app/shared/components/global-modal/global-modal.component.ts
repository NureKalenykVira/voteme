import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { CommonModule, Location } from '@angular/common';
import { Router } from '@angular/router';
import { ModalService } from '../../../core/services/modal.service';
import { AuthStorageService } from '../../../core/services/auth-storage.service';
import { TranslatePipe } from '@ngx-translate/core';

@Component({
  selector: 'app-global-modal',
  standalone: true,
  imports: [CommonModule, TranslatePipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './global-modal.component.html',
  styleUrl: './global-modal.component.scss',
})
export class GlobalModalComponent {
  protected readonly modal = inject(ModalService);
  private readonly router = inject(Router);
  private readonly auth = inject(AuthStorageService);
  private readonly location = inject(Location);

  onLogin(): void {
    this.auth.clearToken();
    this.modal.close();
    this.router.navigate(['/auth/login']);
  }

  onGoHome(): void {
    this.modal.close();
    this.location.back();
  }
}
