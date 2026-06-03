import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import {
  AbstractControl,
  FormBuilder,
  FormGroup,
  ReactiveFormsModule,
  ValidationErrors,
  Validators,
} from '@angular/forms';
import { HttpErrorResponse } from '@angular/common/http';
import { ActivatedRoute, Router } from '@angular/router';
import { TranslatePipe, TranslateService } from '@ngx-translate/core';
import { AuthLayoutComponent } from '../../../../shared/ui/auth-layout/auth-layout.component';
import { TextInputComponent } from '../../../../shared/ui/text-input/text-input.component';
import { PasswordInputComponent } from '../../../../shared/ui/password-input/password-input.component';
import { CheckboxComponent } from '../../../../shared/ui/checkbox/checkbox.component';
import { PrimaryButtonComponent } from '../../../../shared/ui/primary-button/primary-button.component';
import { SecondaryButtonComponent } from '../../../../shared/ui/secondary-button/secondary-button.component';
import { AuthApiService } from '../../services/auth-api.service';
import { containsLetter } from '../../../../shared/validators/password.validators';

function passwordMatchValidator(control: AbstractControl): ValidationErrors | null {
  const password = control.get('password');
  const confirm = control.get('confirmPassword');
  if (!password || !confirm) return null;
  return password.value === confirm.value ? null : { passwordMismatch: true };
}

@Component({
  selector: 'app-register',
  standalone: true,
  imports: [
    CommonModule,
    ReactiveFormsModule,
    TranslatePipe,
    AuthLayoutComponent,
    TextInputComponent,
    PasswordInputComponent,
    CheckboxComponent,
    PrimaryButtonComponent,
    SecondaryButtonComponent,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './register.component.html',
  styleUrl: './register.component.scss',
})
export class RegisterComponent {
  private readonly fb = inject(FormBuilder);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);
  private readonly authApi = inject(AuthApiService);
  private readonly translate = inject(TranslateService);

  readonly loading = signal(false);
  readonly serverError = signal('');
  readonly formState = signal<'form' | 'success'>('form');

  readonly form: FormGroup = this.fb.group(
    {
      fullName: ['', [Validators.required, Validators.minLength(2)]],
      email: ['', [Validators.required, Validators.email]],
      password: ['', [Validators.required, Validators.minLength(8), containsLetter]],
      confirmPassword: ['', Validators.required],
      terms: [false, Validators.requiredTrue],
    },
    { validators: passwordMatchValidator },
  );

  onSubmit(): void {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    this.loading.set(true);
    this.serverError.set('');
    const fullName: string = this.form.get('fullName')!.value;
    this.authApi
      .register({
        email: this.form.get('email')!.value,
        password: this.form.get('password')!.value,
        full_name: fullName?.trim() ? fullName.trim() : null,
      })
      .subscribe({
        next: () => {
          this.loading.set(false);
          this.formState.set('success');
        },
        error: (err: HttpErrorResponse) => {
          this.loading.set(false);
          this.serverError.set(
            err.status === 409
              ? this.translate.instant('auth.register.errorDuplicate')
              : this.translate.instant('auth.register.errorGeneric'),
          );
        },
      });
  }

  goToLogin(): void {
    const returnUrl = this.route.snapshot.queryParams['returnUrl'];
    const extras = returnUrl ? { queryParams: { returnUrl } } : {};
    this.router.navigate(['/auth/login'], extras);
  }
}
