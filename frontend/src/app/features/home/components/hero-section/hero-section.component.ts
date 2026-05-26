import { ChangeDetectionStrategy, Component } from '@angular/core';
import { RouterLink } from '@angular/router';
import { HeroCardComponent } from '../hero-card/hero-card.component';

@Component({
  selector: 'app-hero-section',
  standalone: true,
  imports: [RouterLink, HeroCardComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './hero-section.component.html',
  styleUrl: './hero-section.component.scss',
})
export class HeroSectionComponent {}
