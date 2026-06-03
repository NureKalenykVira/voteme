import { ChangeDetectionStrategy, Component } from '@angular/core';
import { RouterLink } from '@angular/router';
import { TranslatePipe } from '@ngx-translate/core';

@Component({
  selector: 'ui-public-footer',
  standalone: true,
  imports: [RouterLink, TranslatePipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './public-footer.component.html',
  styleUrl: './public-footer.component.scss',
})
export class PublicFooterComponent {}
