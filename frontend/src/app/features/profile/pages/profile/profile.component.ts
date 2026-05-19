import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { CommonModule, DatePipe } from '@angular/common';
import { Router } from '@angular/router';
import { HttpErrorResponse } from '@angular/common/http';
import { PrimaryButtonComponent } from '../../../../shared/ui/primary-button/primary-button.component';
import { AuthApiService } from '../../../auth/services/auth-api.service';
import { AuthStorageService } from '../../../../core/services/auth-storage.service';
import { Role, UserResponse } from '../../../auth/models/auth.models';

type ProfileState = 'loading' | 'ready' | 'error';

@Component({
  selector: 'app-profile',
  standalone: true,
  imports: [CommonModule, DatePipe, PrimaryButtonComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './profile.component.html',
  styleUrl: './profile.component.scss',
})
export class ProfileComponent implements OnInit {
  private readonly authApi = inject(AuthApiService);
  private readonly storage = inject(AuthStorageService);
  private readonly router = inject(Router);

  readonly state = signal<ProfileState>('loading');
  readonly user = signal<UserResponse | null>(null);

  ngOnInit(): void {
    this.loadProfile();
  }

  private loadProfile(): void {
    this.state.set('loading');
    this.authApi.me().subscribe({
      next: (user) => {
        this.user.set(user);
        this.state.set('ready');
      },
      error: (_err: HttpErrorResponse) => {
        this.state.set('error');
      },
    });
  }

  roleLabel(role: Role): string {
    switch (role) {
      case 'global_admin':
        return 'Global admin';
      case 'organizer':
        return 'Organizer';
      case 'voter':
        return 'Voter';
      case 'auditor':
        return 'Auditor';
    }
  }

  onLogout(): void {
    this.storage.clearToken();
    this.router.navigate(['/auth/login']);
  }
}
