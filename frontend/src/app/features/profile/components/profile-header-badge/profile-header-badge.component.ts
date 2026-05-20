import { ChangeDetectionStrategy, Component, Input } from '@angular/core';

@Component({
  selector: 'app-profile-header-badge',
  standalone: true,
  imports: [],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './profile-header-badge.component.html',
  styleUrl: './profile-header-badge.component.scss',
})
export class ProfileHeaderBadgeComponent {
  @Input() label: string = '';
  @Input() variant: 'purple' | 'lime' = 'purple';
}
