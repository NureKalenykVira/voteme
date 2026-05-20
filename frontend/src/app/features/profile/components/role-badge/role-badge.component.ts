import { ChangeDetectionStrategy, Component, Input } from '@angular/core';

@Component({
  selector: 'app-role-badge',
  standalone: true,
  imports: [],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './role-badge.component.html',
  styleUrl: './role-badge.component.scss',
})
export class RoleBadgeComponent {
  @Input() role!: string;

  get roleLabel(): string {
    switch (this.role) {
      case 'global_admin':
        return 'Global admin';
      case 'organizer':
        return 'Organizer';
      case 'voter':
        return 'Voter';
      case 'auditor':
        return 'Auditor';
      default:
        return this.role;
    }
  }
}
