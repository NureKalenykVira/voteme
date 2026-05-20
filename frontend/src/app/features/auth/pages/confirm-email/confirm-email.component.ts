import {
  ChangeDetectionStrategy, Component, OnInit, inject, signal,
} from '@angular/core';
import { NgIf } from '@angular/common';
import { ActivatedRoute, Router } from '@angular/router';
import { AuthLayoutComponent, DecoWord } from '../../../../shared/ui/auth-layout/auth-layout.component';
import { PrimaryButtonComponent } from '../../../../shared/ui/primary-button/primary-button.component';
import { SecondaryButtonComponent } from '../../../../shared/ui/secondary-button/secondary-button.component';
import { AuthApiService } from '../../services/auth-api.service';

@Component({
  selector: 'app-confirm-email',
  standalone: true,
  imports: [NgIf, AuthLayoutComponent, PrimaryButtonComponent, SecondaryButtonComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './confirm-email.component.html',
  styleUrl: './confirm-email.component.scss',
})
export class ConfirmEmailComponent implements OnInit {
  private readonly route   = inject(ActivatedRoute);
  private readonly router  = inject(Router);
  private readonly authApi = inject(AuthApiService);

  readonly vector = '/assets/auth/login_vector.svg';
  readonly decoWords: DecoWord[] = [
    { text: 'Vote', cls: 'deco-vote' },
    { text: 'ME',   cls: 'deco-me'   },
  ];

  readonly state = signal<'loading' | 'success' | 'error'>('loading');

  ngOnInit(): void {
    const token = this.route.snapshot.queryParamMap.get('token');
    if (!token) { this.state.set('error'); return; }
    this.authApi.confirmEmail(token).subscribe({
      next: () => this.state.set('success'),
      error: () => this.state.set('error'),
    });
  }

  goToLogin(): void    { this.router.navigate(['/auth/login']); }
  goToRegister(): void { this.router.navigate(['/auth/register']); }
}
