import { ChangeDetectionStrategy, Component, Input } from '@angular/core';
import { NgFor, NgClass } from '@angular/common';

export interface DecoWord {
  text: string;
  cls: string;
}

@Component({
  selector: 'ui-auth-layout',
  standalone: true,
  imports: [NgFor, NgClass],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './auth-layout.component.html',
  styleUrl: './auth-layout.component.scss',
})
export class AuthLayoutComponent {
  @Input() vector = '/assets/auth/register_vector.svg';
  @Input() vectorLogin = false;
  @Input() decoWords: DecoWord[] = [
    { text: 'Join', cls: 'deco-join' },
    { text: 'Vote', cls: 'deco-vote' },
    { text: 'ME',   cls: 'deco-me'   },
  ];
}
