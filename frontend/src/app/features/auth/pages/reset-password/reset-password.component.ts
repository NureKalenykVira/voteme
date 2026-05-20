import {
  ChangeDetectionStrategy,
  Component,
  OnInit,
  inject,
  signal,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import {
  AbstractControl,
  FormBuilder,
  ReactiveFormsModule,
  ValidationErrors,
  Validators,
} from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { AuthApiService } from '../../services/auth-api.service';
import { ToastService } from '../../../../shared/ui/toast/toast.service';
import { containsLetter } from '../../../../shared/validators/password.validators';

function passwordsMatch(group: AbstractControl): ValidationErrors | null {
  const pw = group.get('newPassword')?.value as string | null;
  const confirm = group.get('confirmPassword')?.value as string | null;
  if (!pw || !confirm) return null;
  return pw === confirm ? null : { passwordMismatch: true };
}

@Component({
  selector: 'app-reset-password',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './reset-password.component.html',
  styleUrl: './reset-password.component.scss',
})
export class ResetPasswordComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly authApi = inject(AuthApiService);
  private readonly toast = inject(ToastService);
  private readonly fb = inject(FormBuilder);

  private token = '';
  readonly saving = signal(false);
  readonly showNew = signal(false);
  readonly showConfirm = signal(false);

  readonly form = this.fb.group(
    {
      newPassword: ['', [Validators.required, Validators.minLength(8), containsLetter]],
      confirmPassword: ['', [Validators.required]],
    },
    { validators: passwordsMatch },
  );

  ngOnInit(): void {
    this.token = this.route.snapshot.queryParamMap.get('token') ?? '';
    if (!this.token) {
      this.toast.error('Invalid reset link.');
      void this.router.navigate(['/auth/login']);
    }
  }

  onSave(): void {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    this.saving.set(true);
    const newPassword = this.form.get('newPassword')!.value as string;
    this.authApi.resetPassword(this.token, newPassword).subscribe({
      next: () => {
        this.toast.success('Password updated! Please log in.');
        void this.router.navigate(['/auth/login']);
      },
      error: () => {
        this.toast.error('Invalid or expired reset link.');
        this.saving.set(false);
      },
    });
  }

  onCancel(): void {
    void this.router.navigate(['/profile']);
  }
}
