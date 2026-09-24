# Corrupted UTKFace age prediction ($R^2$)

Higher is better; negative values are valid. Values are author-reported aggregates at severity 5. **Oracle†** uses target labels and is not a same-information competitor.

| Method | Defocus | Motion | Zoom | Contrast | Elastic | JPEG | Pixelate | Gaussian | Impulse | Shot | Bright | Fog | Snow | Mean |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Source | 0.410 | 0.159 | 0.658 | -3.906 | 0.711 | 0.069 | 0.595 | -2.536 | -2.539 | -2.522 | 0.661 | -0.029 | -0.544 | -0.678 |
| TTT | 0.748 | 0.761 | 0.773 | 0.778 | 0.826 | 0.772 | 0.861 | 0.525 | 0.532 | 0.477 | 0.775 | 0.397 | 0.493 | 0.671 |
| BN-Adapt | 0.727 | 0.759 | 0.763 | 0.702 | 0.826 | 0.778 | 0.850 | 0.510 | 0.510 | 0.446 | 0.790 | 0.392 | 0.452 | 0.654 |
| FR | 0.794 | 0.839 | 0.849 | 0.756 | 0.899 | 0.825 | 0.946 | 0.509 | 0.522 | 0.458 | 0.861 | 0.408 | 0.428 | 0.700 |
| RSD | 0.789 | 0.833 | 0.851 | 0.749 | 0.897 | 0.825 | 0.941 | 0.502 | 0.503 | 0.445 | 0.862 | 0.419 | 0.500 | 0.701 |
| **SSA (ours)** | 0.803 | 0.839 | 0.851 | 0.792 | 0.899 | 0.829 | 0.943 | 0.580 | 0.592 | 0.560 | 0.863 | 0.440 | 0.517 | 0.731 |
| Oracle† | 0.856 | 0.890 | 0.889 | 0.862 | 0.917 | 0.873 | 0.960 | 0.635 | 0.652 | 0.635 | 0.895 | 0.519 | 0.671 | 0.789 |

Notes: Source is unadapted. SSA adapts only normalization affine scale/shift parameters while keeping the regression head and all other parameters fixed. No target labels or source examples are used during adaptation; precomputed source statistics are used. No uncertainty is shown because per-run observations and sampling uncertainty were not supplied. Source: arXiv:2410.03263v1, Table S4.T4.
