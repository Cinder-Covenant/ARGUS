# Credits, terms and scope

CT source: Vesuvius Challenge, PHerc0268, `20251110183117-8.640um-1.2m-116keV-masked.zarr`, level 0. This package contributes crop curation/provenance and portable access code; it does not claim original CT acquisition, fiber annotations or ink truth. Selection/filter/training work originated in Ryan Gurganious's retained Vesuvius research repository. No CT pixels or model weights are distributed here.

The official [data documentation](https://scrollprize.org/data) lists CC-BY-NC 4.0 unless a specific asset says otherwise, describes original-host partial Zarr access and supplies the newer Vesuvius CT citation. The live [data-server license](https://dl.ash2txt.org/LICENSE.txt) requires written Vesuvius Challenge approval for redistribution. Both were read on September 30, 2026. Exact application to this PHerc0268 S3 asset is unresolved; this package does not resolve the conflict or grant rehosting permission. The default command is an offline plan. A researcher must review their applicable original-host terms before explicitly fetching.

Use the citation for **Vesuvius Challenge — CT Scans of Herculaneum Papyri** on the data documentation page, with the exact PHerc0268 scan URI and this selection recipe. Do not attribute this newer scan to the legacy EduceLab acquisition merely because the portal also hosts that dataset.

The source and metadata in this starter are offered under its MIT code/documentation license. The retained Vesuvius repository license is Ryan's MIT code license; current ARGUS public code uses Apache-2.0. Those licenses do not license CT pixels or settle trained-weight/data terms. This package contains neither payload. Integration into ARGUS must preserve applicable notices and keep data terms separate.

The original selection's density criterion was nonzero fraction >=0.5, a material-content gate. It is not an ink or fiber label. Actual per-field density values were not retained in this manifest. The source is isotropic raw CT at 8.640 micrometers, unlike surface-relative ink-evaluation inputs.

Preparation performed no original-host fetch, real CT decoding, visualization, inference, training, checkpoint loading, reading claim or Google-form submission. No target CT pixels or model weights are included for upload. Hashes cover retained compressed bytes; they do not prove decoded scientific content. Synthetic tests and a mocked source verify code paths independently of real CT. Remote layout/access remains untested; the level `0` layout is supported by the original retained `open_pyramid_level` source.
