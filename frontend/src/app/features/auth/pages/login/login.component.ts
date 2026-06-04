import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { HttpErrorResponse } from '@angular/common/http';
import { ActivatedRoute, Router } from '@angular/router';
import { TranslatePipe, TranslateService } from '@ngx-translate/core';
import {
  AuthLayoutComponent,
  DecoWord,
} from '../../../../shared/ui/auth-layout/auth-layout.component';
import { TextInputComponent } from '../../../../shared/ui/text-input/text-input.component';
import { PasswordInputComponent } from '../../../../shared/ui/password-input/password-input.component';
import { PrimaryButtonComponent } from '../../../../shared/ui/primary-button/primary-button.component';
import { SecondaryButtonComponent } from '../../../../shared/ui/secondary-button/secondary-button.component';
import { AuthApiService } from '../../services/auth-api.service';
import { AuthStorageService } from '../../../../core/services/auth-storage.service';
import { containsLetter } from '../../../../shared/validators/password.validators';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [
    CommonModule,
    ReactiveFormsModule,
    TranslatePipe,
    AuthLayoutComponent,
    TextInputComponent,
    PasswordInputComponent,
    PrimaryButtonComponent,
    SecondaryButtonComponent,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './login.component.html',
  styleUrl: './login.component.scss',
})
export class LoginComponent {
  private readonly fb = inject(FormBuilder);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);
  private readonly authApi = inject(AuthApiService);
  private readonly storage = inject(AuthStorageService);
  private readonly translate = inject(TranslateService);

  readonly loading = signal(false);
  readonly serverError = signal('');

  readonly vector = '/assets/auth/login_vector.svg';
  readonly decoWords: DecoWord[] = [
    { text: 'Vote', cls: 'deco-vote' },
    { text: 'ME', cls: 'deco-me' },
  ];

  readonly form: FormGroup = this.fb.group({
    email: ['', [Validators.required, Validators.email]],
    password: ['', [Validators.required, Validators.minLength(8), containsLetter]],
  });

  onSubmit(): void {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    this.loading.set(true);
    this.serverError.set('');
    this.authApi
      .login({
        email: this.form.get('email')!.value,
        password: this.form.get('password')!.value,
      })
      .subscribe({
        next: (resp) => {
          this.storage.setToken(resp.access_token);
          const returnUrl = this.route.snapshot.queryParams['returnUrl'];
          if (returnUrl) {
            this.router.navigate([returnUrl]);
          } else if (this.storage.getRole() === 'global_admin') {
            this.router.navigate(['/admin/users']);
          } else {
            this.router.navigate(['/home']);
          }
        },
        error: (err: HttpErrorResponse) => {
          this.loading.set(false);
          if (err.status === 401) this.serverError.set(this.translate.instant('auth.login.errorInvalid'));
          else if (err.status === 403)
            this.serverError.set(this.translate.instant('auth.login.errorConfirm'));
          else this.serverError.set(this.translate.instant('auth.login.errorGeneric'));
        },
      });
  }

  onGoogleLogin(): void {
    // TODO: wire Google OAuth
    console.log('Google login');
  }

  goToRegister(): void {
    this.router.navigate(['/auth/register']);
  }
}
