/**
 * Apple touch icon — 180×180 PNG generated on the fly from the Strata
 * mark so iOS bookmarks / Safari "Add to Home Screen" pick up the brand.
 *
 * Same colours as app/icon.svg. ImageResponse from next/og handles the
 * SVG-to-PNG conversion at build/request time.
 */
import { ImageResponse } from 'next/og';

export const size = { width: 180, height: 180 };
export const contentType = 'image/png';

export default function AppleIcon() {
  return new ImageResponse(
    (
      <div
        style={{
          width: '100%',
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          background: '#2c7d6e',
          borderRadius: 40,
          gap: 18,
        }}
      >
        <div style={{ width: 88, height: 18, borderRadius: 9, background: '#fbfaf7' }} />
        <div
          style={{
            width: 88,
            height: 18,
            borderRadius: 9,
            background: '#fbfaf7',
            opacity: 0.55,
          }}
        />
      </div>
    ),
    { ...size },
  );
}
