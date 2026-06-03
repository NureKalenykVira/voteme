import {
  ChangeDetectionStrategy,
  Component,
  OnInit,
  computed,
  inject,
  signal,
} from '@angular/core';
import { CommonModule, Location } from '@angular/common';
import { environment } from '../../../../../environments/environment';
import { FormBuilder, FormControl, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router } from '@angular/router';
import { HttpErrorResponse } from '@angular/common/http';
import { TranslateService, TranslatePipe } from '@ngx-translate/core';
import { AuthApiService } from '../../../auth/services/auth-api.service';
import { AuthStorageService } from '../../../../core/services/auth-storage.service';
import { ToastService } from '../../../../shared/ui/toast/toast.service';
import { UserResponse } from '../../../auth/models/auth.models';
import { ProfileAvatarComponent } from '../../components/profile-avatar/profile-avatar.component';
import { ProfileHeaderBadgeComponent } from '../../components/profile-header-badge/profile-header-badge.component';
import { RoleBadgeComponent } from '../../components/role-badge/role-badge.component';
import { ActivityStatRowComponent } from '../../components/activity-stat-row/activity-stat-row.component';
import { ActivityLinkButtonComponent } from '../../components/activity-link-button/activity-link-button.component';

type ProfileState = 'loading' | 'ready' | 'error';

@Component({
  selector: 'app-profile',
  standalone: true,
  imports: [
    CommonModule,
    ReactiveFormsModule,
    TranslatePipe,
    ProfileAvatarComponent,
    ProfileHeaderBadgeComponent,
    RoleBadgeComponent,
    ActivityStatRowComponent,
    ActivityLinkButtonComponent,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './profile.component.html',
  styleUrl: './profile.component.scss',
})
export class ProfileComponent implements OnInit {
  private readonly authApi = inject(AuthApiService);
  private readonly storage = inject(AuthStorageService);
  private readonly router = inject(Router);
  private readonly location = inject(Location);
  private readonly fb = inject(FormBuilder);
  private readonly toastService = inject(ToastService);
  private readonly translate = inject(TranslateService);

  readonly state = signal<ProfileState>('loading');
  readonly user = signal<UserResponse | null>(null);
  readonly avatarPreview = signal<string | null>(null);
  readonly resolvedAvatarUrl = computed(() => {
    const url = this.user()?.avatar_url ?? null;
    if (!url) return null;
    // Prepend API base URL for relative paths returned by backend
    return url.startsWith('/') ? `${environment.apiUrl}${url}` : url;
  });
  readonly loading = signal(false);
  readonly confirmDelete = signal(false);
  readonly deleting = signal(false);
  readonly showResetModal = signal(false);
  readonly resetLinkSending = signal(false);

  readonly fullNameForm = this.fb.group({
    fullName: ['', [Validators.required, Validators.minLength(2)]],
  });

  get fullNameControl(): FormControl {
    return this.fullNameForm.get('fullName') as FormControl;
  }

  ngOnInit(): void {
    this.loadProfile();
  }

  private loadProfile(): void {
    this.state.set('loading');
    this.authApi.me().subscribe({
      next: (resp: UserResponse) => {
        if (resp.role !== this.storage.getRole()) {
          this.onLogout();
          return;
        }
        this.user.set(resp);
        this.fullNameForm.patchValue({ fullName: resp.full_name ?? '' });
        this.state.set('ready');
      },
      error: (_err: HttpErrorResponse) => {
        this.state.set('error');
      },
    });
  }

  onFileSelected(file: File): void {
    const reader = new FileReader();
    reader.onload = (e: ProgressEvent<FileReader>) => {
      this.avatarPreview.set(e.target?.result as string);
    };
    reader.readAsDataURL(file);

    this.authApi.uploadAvatar(file).subscribe({
      next: (resp) => {
        this.user.set(resp);
        this.toastService.success(this.translate.instant('profile.toast.avatarUpdated'));
      },
      error: () => {
        this.toastService.error(this.translate.instant('profile.toast.avatarFailed'));
      },
    });
  }

  onAvatarReset(): void {
    this.avatarPreview.set(null);
  }

  onSaveChanges(): void {
    if (this.fullNameForm.invalid) {
      this.fullNameForm.markAllAsTouched();
      return;
    }
    this.loading.set(true);
    const fullName = this.fullNameControl.value?.trim() || null;
    this.authApi.updateProfile({ full_name: fullName }).subscribe({
      next: (resp) => {
        this.user.set(resp);
        this.toastService.success(this.translate.instant('profile.toast.saved'));
        this.loading.set(false);
      },
      error: () => {
        this.toastService.error(this.translate.instant('profile.toast.saveFailed'));
        this.loading.set(false);
      },
    });
  }

  onLogout(): void {
    this.storage.clearToken();
    this.router.navigate(['/auth/login']);
  }

  onGoHome(): void {
    this.location.back();
  }

  onForgotPassword(): void {
    this.showResetModal.set(true);
  }

  onCancelReset(): void {
    this.showResetModal.set(false);
  }

  onSendResetLink(): void {
    const email = this.user()?.email;
    if (!email) return;
    this.resetLinkSending.set(true);
    this.authApi.forgotPassword(email).subscribe({
      next: () => {
        this.toastService.success(this.translate.instant('profile.toast.resetSent'));
        this.showResetModal.set(false);
        this.resetLinkSending.set(false);
      },
      error: () => {
        this.toastService.error(this.translate.instant('profile.toast.resetFailed'));
        this.resetLinkSending.set(false);
      },
    });
  }

  onDeleteAccount(): void {
    this.confirmDelete.set(true);
  }

  onConfirmDelete(): void {
    this.deleting.set(true);
    this.authApi.deleteAccount().subscribe({
      next: () => {
        this.storage.clearToken();
        this.router.navigate(['/auth/register']);
      },
      error: () => {
        this.deleting.set(false);
        this.confirmDelete.set(false);
        this.toastService.error(this.translate.instant('profile.toast.deleteFailed'));
      },
    });
  }

  onCancelDelete(): void {
    this.confirmDelete.set(false);
  }
}
