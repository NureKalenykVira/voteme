import { ChangeDetectionStrategy, Component } from '@angular/core';
import { PublicHeaderComponent } from '../../shared/layout/public-header/public-header.component';
import { PublicFooterComponent } from '../../shared/layout/public-footer/public-footer.component';

@Component({
  selector: 'app-terms',
  standalone: true,
  imports: [PublicHeaderComponent, PublicFooterComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './terms.component.html',
  styleUrls: ['./terms.component.scss'],
})
export class TermsComponent {}
