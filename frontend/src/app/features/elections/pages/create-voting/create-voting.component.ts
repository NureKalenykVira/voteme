import {
  ChangeDetectionStrategy,
  ChangeDetectorRef,
  Component,
  inject,
  OnInit,
  signal,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import {
  AbstractControl,
  FormArray,
  FormBuilder,
  FormGroup,
  ReactiveFormsModule,
  ValidationErrors,
  Validators,
} from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { TranslatePipe, TranslateService } from '@ngx-translate/core';
import { catchError, concatMap, forkJoin, from, of, switchMap, tap, toArray } from 'rxjs';
import { VotingOptionCardComponent } from '../../../../shared/ui/voting-option-card/voting-option-card.component';
import { TextInputComponent } from '../../../../shared/ui/text-input/text-input.component';
import { DatePickerComponent } from '../../../../shared/ui/date-picker/date-picker.component';
import { TimePickerComponent } from '../../../../shared/ui/time-picker/time-picker.component';
import { AuthApiService } from '../../../auth/services/auth-api.service';
import { AuthStorageService } from '../../../../core/services/auth-storage.service';
import { ElectionsApiService } from '../../services/elections-api.service';
import {
  BallotOptionCreateRequest,
  BallotOptionResponse,
  BallotOptionUpdateRequest,
  CreateElectionRequest,
  VotingDetailResponse,
} from '../../models/elections.models';
import { environment } from '../../../../../environments/environment';
import { ToastService } from '../../../../shared/ui/toast/toast.service';

function notInPastValidator(
  dateControl: string,
  timeControl: string,
  errorKey: string,
): (group: AbstractControl) => ValidationErrors | null {
  return (group: AbstractControl): ValidationErrors | null => {
    const date = group.get(dateControl)?.value as string;
    const time = group.get(timeControl)?.value as string;
    if (!date || !time) return null;
    const dt = new Date(`${date}T${time}`);
    return dt < new Date() ? { [errorKey]: true } : null;
  };
}

@Component({
  selector: 'app-create-voting',
  standalone: true,
  imports: [
    CommonModule,
    ReactiveFormsModule,
    VotingOptionCardComponent,
    TextInputComponent,
    DatePickerComponent,
    TimePickerComponent,
    TranslatePipe,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './create-voting.component.html',
  styleUrls: ['./create-voting.component.scss'],
})
export class CreateVotingComponent implements OnInit {
  private readonly fb = inject(FormBuilder);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);
  private readonly cdr = inject(ChangeDetectorRef);
  private readonly authApi = inject(AuthApiService);
  private readonly authStorage = inject(AuthStorageService);
  private readonly electionsApi = inject(ElectionsApiService);
  private readonly toast = inject(ToastService);
  private readonly translate = inject(TranslateService);
  readonly isEditMode = !!this.route.snapshot.paramMap.get('id');
  readonly electionStatus = signal<string>('draft');

  private optionIds: (string | null)[] = [];
  private photoFiles: (File | null)[] = [];
  private existingPhotoUrls: string[] = [];
  private invitationCode = '';

  readonly form = this.fb.group({
    title: ['', Validators.required],
    description: [''],
    startDate: ['', Validators.required],
    startTime: ['', Validators.required],
    endDate: ['', Validators.required],
    endTime: ['', Validators.required],
    options: this.fb.array([this.createOption(), this.createOption()]),
  });

  ngOnInit(): void {
    // Past-date validators only apply when creating. In edit mode existing
    // elections may legitimately have start/end dates in the past.
    if (!this.isEditMode) {
      this.form.addValidators([
        notInPastValidator('startDate', 'startTime', 'pastStartDatetime'),
        notInPastValidator('endDate', 'endTime', 'pastEndDatetime'),
      ]);
      this.form.updateValueAndValidity();
    }
    this.form.statusChanges.subscribe(() => this.cdr.markForCheck());

    if (this.isEditMode) {
      this.loadElection();
    }
  }

  private loadElection(): void {
    const id = this.route.snapshot.paramMap.get('id');
    if (!id) return;

    this.electionsApi.getDetail(id).subscribe({
      next: (election: VotingDetailResponse) => {
        const [startDate, startTime] = this.splitIso(election.start_date_time);
        const [endDate, endTime] = this.splitIso(election.end_date_time);

        this.form.patchValue({
          title: election.title,
          description: election.description ?? '',
          startDate,
          startTime,
          endDate,
          endTime,
        });

        this.electionStatus.set(election.status);
        this.invitationCode = election.invitation_code ?? '';

        this.options.clear();
        this.optionIds = [];
        this.photoFiles = [];
        this.existingPhotoUrls = [];
        const sorted = [...election.options].sort((a, b) => a.order_index - b.order_index);
        sorted.forEach((opt: BallotOptionResponse) => {
          const group = this.createOption();
          group.patchValue({
            title: opt.title,
            description: opt.description ?? '',
            photo: '',
          });
          this.options.push(group);
          this.optionIds.push(opt.id);
          this.photoFiles.push(null);
          this.existingPhotoUrls.push(opt.photo_url ?? '');
        });
        if (this.options.length === 0) {
          this.addOption();
          this.addOption();
        }

        this.cdr.markForCheck();
      },
      error: (err) => {
        console.error('Failed to load election for edit', err);
        this.toast.error(this.translate.instant('createVoting.toastFailedLoad'));
      },
    });
  }

  private splitIso(iso: string): [string, string] {
    if (!iso) return ['', ''];
    const d = new Date(iso);
    if (isNaN(d.getTime())) return ['', ''];
    const pad = (n: number) => n.toString().padStart(2, '0');
    const date = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
    const time = `${pad(d.getHours())}:${pad(d.getMinutes())}`;
    return [date, time];
  }

  get options(): FormArray {
    return this.form.get('options') as FormArray;
  }

  getOptionGroup(index: number): FormGroup {
    return this.options.at(index) as FormGroup;
  }

  createOption(): FormGroup {
    return this.fb.group({
      title: ['', Validators.required],
      description: [''],
      photo: [''],
    });
  }

  addOption(): void {
    this.options.push(this.createOption());
    this.optionIds.push(null);
    this.photoFiles.push(null);
    this.existingPhotoUrls.push('');
  }

  removeOption(i: number): void {
    if (this.options.length > 2) {
      this.options.removeAt(i);
      this.optionIds.splice(i, 1);
      this.photoFiles.splice(i, 1);
      this.existingPhotoUrls.splice(i, 1);
    }
  }

  getExistingPhotoUrl(i: number): string {
    const url = this.existingPhotoUrls[i] ?? '';
    if (!url) return '';
    return url.startsWith('/') ? `${environment.apiUrl}${url}` : url;
  }

  onPhotoSelected(i: number, file: File | null): void {
    this.photoFiles[i] = file;
  }

  private toIso(date: string, time: string): string {
    return new Date(`${date}T${time}:00`).toISOString();
  }

  onSubmit(action: 'draft' | 'published'): void {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }

    if (this.isEditMode) {
      this.submitEdit(action);
      return;
    }

    const v = this.form.value;

    const electionPayload: CreateElectionRequest = {
      title: v.title!,
      description: v.description ?? undefined,
      access_type: 'private',
      is_anonymous: false,
      start_date_time: this.toIso(v.startDate!, v.startTime!),
      end_date_time: this.toIso(v.endDate!, v.endTime!),
    };

    const optionPayloads: BallotOptionCreateRequest[] = (v.options ?? []).map(
      (o: { title?: string; description?: string }) => ({
        title: o.title!,
        description: o.description ?? undefined,
      }),
    );

    this.authApi
      .becomeOrganizer()
      .pipe(
        catchError((err) => {
          if (err.status === 409) return from([null]);
          throw err;
        }),
        switchMap((resp) => {
          if (resp && 'access_token' in resp) {
            this.authStorage.setToken(resp.access_token);
          }
          return this.electionsApi.create(electionPayload);
        }),
        switchMap((election) => {
          const options$ = optionPayloads.length
            ? from(optionPayloads.map((opt, idx) => ({ opt, idx }))).pipe(
                concatMap(({ opt, idx }) =>
                  this.electionsApi.createOption(election.id, opt).pipe(
                    switchMap((created) => {
                      const photoFile = this.photoFiles[idx] ?? null;
                      if (!photoFile || !created?.id) return of(null);
                      return this.electionsApi
                        .uploadOptionPhoto(election.id, created.id, photoFile)
                        .pipe(
                          catchError((err) => {
                            console.error('Failed to upload photo for new option', err);
                            return of(null);
                          }),
                        );
                    }),
                  ),
                ),
                toArray(),
              )
            : from([[]]);
          return options$.pipe(
            switchMap(() => {
              if (action === 'published') {
                return this.electionsApi.publish(election.id).pipe(
                  catchError((err) => {
                    console.error('Publish failed, election remains draft', err);
                    return from([null]);
                  }),
                );
              }
              return from([null]);
            }),
            tap(() =>
              this.toast.success(
                action === 'published'
                  ? this.translate.instant('createVoting.toastPublished')
                  : this.translate.instant('createVoting.toastCreated'),
              ),
            ),
            switchMap(() => from(this.router.navigate(['/elections', election.id, 'invite']))),
          );
        }),
      )
      .subscribe({
        error: (err) => {
          console.error('Submit failed', err);
          this.toast.error(err?.error?.detail ?? this.translate.instant('createVoting.toastFailedSave'));
        },
      });
  }

  private submitEdit(action: 'draft' | 'published'): void {
    const id = this.route.snapshot.paramMap.get('id');
    if (!id) return;

    const v = this.form.value;

    const electionPayload: Partial<CreateElectionRequest> = {
      title: v.title!,
      description: v.description ?? undefined,
      access_type: 'private',
      is_anonymous: false,
      start_date_time: this.toIso(v.startDate!, v.startTime!),
      end_date_time: this.toIso(v.endDate!, v.endTime!),
    };

    const optionValues = (v.options ?? []) as { title?: string; description?: string }[];

    this.electionsApi
      .update(id, electionPayload)
      .pipe(
        catchError((err) => {
          console.error('Failed to update election', err);
          return of(null);
        }),
        switchMap(() =>
          from(optionValues.map((value, index) => ({ value, index }))).pipe(
            concatMap(({ value, index }) => this.persistOption(id, value, index)),
            toArray(),
          ),
        ),
        switchMap(() => {
          if (action === 'published' && this.electionStatus() === 'draft') {
            return this.electionsApi.publish(id).pipe(
              catchError((err) => {
                if (err.status === 409) return of(null); // already published — fine
                console.error('Publish failed in edit mode', err);
                return of(null);
              }),
            );
          }
          return of(null);
        }),
        tap(() =>
          this.toast.success(
            action === 'published'
              ? this.translate.instant('createVoting.toastPublished')
              : this.translate.instant('createVoting.toastCreated'),
          ),
        ),
        switchMap(() => from(this.router.navigate(['/join', this.invitationCode]))),
      )
      .subscribe({
        error: (err) => {
          console.error('Edit submit failed', err);
          this.toast.error(err?.error?.detail ?? this.translate.instant('createVoting.toastFailedUpdate'));
        },
      });
  }

  private persistOption(
    electionId: string,
    value: { title?: string; description?: string },
    index: number,
  ) {
    const payload: BallotOptionUpdateRequest = {
      title: value.title!,
      description: value.description ?? undefined,
    };
    const existingId = this.optionIds[index] ?? null;
    const photoFile = this.photoFiles[index] ?? null;

    const ensureOption$ = existingId
      ? this.electionsApi.updateOption(electionId, existingId, payload).pipe(
          catchError((err) => {
            console.error('Failed to update option', err);
            return of(null);
          }),
          switchMap(() => of(existingId)),
        )
      : this.electionsApi
          .createOption(electionId, { title: payload.title!, description: payload.description })
          .pipe(
            catchError((err) => {
              console.error('Failed to create option', err);
              return of(null);
            }),
            switchMap((created) => of(this.extractOptionId(created))),
          );

    return ensureOption$.pipe(
      switchMap((optionId) => {
        if (!optionId || !photoFile) return of(null);
        return this.electionsApi.uploadOptionPhoto(electionId, optionId, photoFile).pipe(
          catchError((err) => {
            console.error('Failed to upload option photo', err);
            return of(null);
          }),
        );
      }),
    );
  }

  private extractOptionId(created: unknown): string | null {
    if (created && typeof created === 'object' && 'id' in created) {
      const id = (created as { id?: unknown }).id;
      return typeof id === 'string' ? id : null;
    }
    return null;
  }

  cancel(): void {
    this.router.navigate(['/home']);
  }

  manageVoters(): void {
    const id = this.route.snapshot.paramMap.get('id');
    if (id) this.router.navigate(['/elections', id, 'voters']);
  }
}
