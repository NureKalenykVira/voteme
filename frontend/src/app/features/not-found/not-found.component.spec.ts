import { TestBed } from '@angular/core/testing';
import { provideTranslateService } from '@ngx-translate/core';
import { NotFoundComponent } from './not-found.component';

describe('NotFoundComponent', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [NotFoundComponent],
      providers: [provideTranslateService()],
    }).compileComponents();
  });

  it('should create', () => {
    const fixture = TestBed.createComponent(NotFoundComponent);
    expect(fixture.componentInstance).toBeTruthy();
  });

  it('renders the title, subtitle and a go-back button', () => {
    const fixture = TestBed.createComponent(NotFoundComponent);
    fixture.detectChanges();
    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelector('.not-found__title')).not.toBeNull();
    expect(el.querySelector('.not-found__subtitle')).not.toBeNull();
    expect(el.querySelector('.not-found__btn')).not.toBeNull();
  });

  it('calls location.back() when the go-back button is clicked', () => {
    const fixture = TestBed.createComponent(NotFoundComponent);
    const backSpy = vi.spyOn(fixture.componentInstance.location, 'back');
    fixture.detectChanges();
    const btn = fixture.nativeElement.querySelector('.not-found__btn') as HTMLButtonElement;
    btn.click();
    expect(backSpy).toHaveBeenCalled();
  });
});
