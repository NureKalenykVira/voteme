import { ChangeDetectionStrategy, Component, inject, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { TranslatePipe, TranslateService } from '@ngx-translate/core';
import { AdminApiService } from '../../services/admin-api.service';
import { BackupResponse, RestoreResponse } from '../../models/admin.models';
import { ToastService } from '../../../../shared/ui/toast/toast.service';

@Component({
  selector: 'app-admin-settings',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, TranslatePipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './admin-settings.component.html',
  styleUrls: ['./admin-settings.component.scss'],
})
export class AdminSettingsComponent implements OnInit {
  private readonly api = inject(AdminApiService);
  private readonly fb = inject(FormBuilder);
  private readonly toast = inject(ToastService);
  private readonly translate = inject(TranslateService);

  readonly lastBackup = signal<BackupResponse | null>(null);
  readonly savingSettings = signal(false);
  readonly creatingBackup = signal(false);
  readonly restoringBackup = signal(false);

  readonly settingsForm = this.fb.group({
    max_free_votings_per_month: [12, [Validators.required, Validators.min(0)]],
    maintenance_mode: [false],
    require_email_verification: [true],
    session_timeout_minutes: [2880, [Validators.required, Validators.min(1)]],
  });

  ngOnInit(): void {
    this.api.getSettings().subscribe({
      next: (data) => {
        this.settingsForm.patchValue(data);
      },
      error: () => {},
    });

    this.api.getBackupInfo().subscribe({
      next: (info) => {
        if (info) this.lastBackup.set(info);
      },
      error: () => {},
    });
  }

  saveSettings(): void {
    if (this.settingsForm.invalid || this.savingSettings()) return;
    this.savingSettings.set(true);
    const val = this.settingsForm.getRawValue();
    this.api
      .updateSettings({
        max_free_votings_per_month: val.max_free_votings_per_month ?? 12,
        maintenance_mode: val.maintenance_mode ?? false,
        require_email_verification: val.require_email_verification ?? true,
        session_timeout_minutes: val.session_timeout_minutes ?? 2880,
      })
      .subscribe({
        next: () => {
          this.savingSettings.set(false);
          this.toast.success(this.translate.instant('admin.settings.saveSettings'));
        },
        error: () => {
          this.savingSettings.set(false);
          this.toast.error('Failed to save settings');
        },
      });
  }

  createBackup(): void {
    if (this.creatingBackup()) return;
    this.creatingBackup.set(true);
    this.api.createBackup().subscribe({
      next: (backup) => {
        this.lastBackup.set(backup);
        this.creatingBackup.set(false);
        this.toast.success(this.translate.instant('admin.settings.createBackup'));
      },
      error: () => {
        this.creatingBackup.set(false);
        this.toast.error('Failed to create backup');
      },
    });
  }

  stepField(field: 'max_free_votings_per_month' | 'session_timeout_minutes', delta: number): void {
    const ctrl = this.settingsForm.get(field);
    if (!ctrl) return;
    const min = field === 'session_timeout_minutes' ? 1 : 0;
    const newVal = Math.max(min, (ctrl.value ?? 0) + delta);
    ctrl.setValue(newVal);
  }

  restoreBackup(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file || this.restoringBackup()) {
      return;
    }
    this.restoringBackup.set(true);
    this.api.restoreBackup(file).subscribe({
      next: (res: RestoreResponse) => {
        this.restoringBackup.set(false);
        input.value = '';
        this.toast.success(
          `${this.translate.instant('admin.settings.restoreBackup')}: ${res.users_imported} users, ${res.votings_imported} votings imported`,
        );
      },
      error: () => {
        this.restoringBackup.set(false);
        input.value = '';
        this.toast.error('Failed to restore backup');
      },
    });
  }

  downloadBackup(): void {
    this.api.downloadBackup().subscribe({
      next: (blob) => {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `voteme-backup-${new Date().toISOString().slice(0, 10)}.json`;
        a.click();
        URL.revokeObjectURL(url);
        this.toast.success('Backup downloaded');
      },
      error: () => {
        this.toast.error('Failed to download backup');
      },
    });
  }
}
