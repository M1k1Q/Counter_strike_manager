Place optimized, versioned player photos here, for example jks-v1-80.webp
and jks-v1-160.webp. This directory deliberately avoids /players, which
Vite proxies to the backend API.

Register available files in src/data/playerImages.json using lowercase
player nicknames (matching the CSV's Player column):

```json
{
  "jks": {
    "thumbnail": "/player-images/jks-v1-80.webp",
    "profile": "/player-images/jks-v1-160.webp"
  }
}
```

A single URL string is also supported. HTTPS CDN URLs work in either format.
Use unique nicknames; if the dataset gains duplicate names, introduce a stable
external identity before mapping their photos. Do not key photos by team,
since players transfer, or by database IDs that can change on reseeding.

Only register files that actually exist. Missing mappings show initials without
making any image request; failed downloads also fall back to initials.
No player photo files were included in the source dataset.

Suggested exports: 80x80 WebP for 40px table avatars, 160x160 WebP for 80px
profile avatars. Aim for thumbnails under 10KB. Obtain photos you can use
and host them here or on your own CDN instead of using profile page URLs.

Production hosting: configure Cache-Control: public, max-age=31536000, immutable
ONLY for versioned image files under /player-images/. Change the filename and
mapping whenever a photo changes. Do not apply this policy to HTML or API
responses. Vite development/preview does not configure production CDN headers.
