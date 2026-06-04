import { ChangeDetectionStrategy, Component, inject, signal, ViewEncapsulation } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormControl } from '@angular/forms';
import { Router } from '@angular/router';
import { TranslatePipe, TranslateService } from '@ngx-translate/core';
import { AuthLayoutComponent, DecoWord } from '../../shared/ui/auth-layout/auth-layout.component';

@Component({
  selector: 'app-join-voting',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, AuthLayoutComponent, TranslatePipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  encapsulation: ViewEncapsulation.None,
  templateUrl: './join-voting.component.html',
  styleUrls: ['./join-voting.component.scss'],
})
export class JoinVotingComponent {
  private readonly router = inject(Router);
  private readonly translate = inject(TranslateService);

  readonly vector = '/assets/auth/login_vector.svg';
  readonly decoWords: DecoWord[] = [
    { text: 'Vote', cls: 'deco-vote' },
    { text: 'ME', cls: 'deco-me' },
  ];

  readonly codeCtrl = new FormControl('');
  readonly linkCtrl = new FormControl('');
  readonly codeError = signal('');
  readonly linkError = signal('');

  joinByCode(): void {
    const code = this.codeCtrl.value?.trim() ?? '';
    if (!code) {
      this.codeError.set(this.translate.instant('join.errorNoCode'));
      return;
    }
    this.codeError.set('');
    this.router.navigate(['/join', code]);
  }

  joinByLink(): void {
    const raw = this.linkCtrl.value?.trim() ?? '';
    if (!raw) {
      this.linkError.set(this.translate.instant('join.errorNoLink'));
      return;
    }
    this.linkError.set('');
    try {
      const url = new URL(raw);
      const parts = url.pathname.split('/').filter(Boolean);
      const code = parts[parts.length - 1];
      if (code) {
        this.router.navigate(['/join', code]);
        return;
      }
    } catch {
      /* not a full URL — fall through */
    }
    // treat raw value as code directly
    this.router.navigate(['/join', raw]);
  }

  goHome(): void {
    this.router.navigate(['/home']);
  }
}
