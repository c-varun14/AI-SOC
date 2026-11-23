# Rights and attribution

| Material | Source and terms | Staging decision |
|---|---|---|
| Team application, integration and documentation | Team ownership and publication authority require confirmation. A team license has yet to be approved. | No project-wide license declaration. Team approval is required before publication. |
| ExecuTorch 1.6.0 | BSD license conditions and copyright notices apply to upstream code and binary redistributions. The exact upstream notice is included. | Build patches and pinned source references are included. Runtime libraries, wheels and binaries are omitted. [Upstream license](https://github.com/pytorch/executorch/blob/v1.6.0/LICENSE) |
| EfficientNetV2-S initialization | Training used torchvision `EfficientNet_V2_S_Weights.DEFAULT`, the ImageNet-1K weight entry. Torchvision code carries its own license. Torchvision separately flags possible restrictions on pre-trained models and their training datasets. | Original and fine-tuned weights are omitted. Review applicable upstream weight and dataset terms before distributing a checkpoint or export. [Torchvision pretrained-model terms](https://github.com/pytorch/vision#disclaimer-on-pre-trained-models) · [Weights enum](https://docs.pytorch.org/vision/stable/models/generated/torchvision.models.efficientnet_v2_s.html) |
| Llama 3.2 1B Instruct | Meta Llama 3.2 Community License and applicable use policy. Check redistribution notice, attribution, and naming conditions in the official terms for any Llama material or product shared. | Original weights, Q4 export and tokenizer are omitted. Recorded output and build documentation are included for review. [Meta license](https://github.com/meta-llama/llama-models/blob/main/models/llama3_2/LICENSE) |
| PharmaVision archive and demo images | Tahir Mahmood, *Pharmaceutical Tablet Defect Dataset*, v1.0, Zenodo DOI 10.5281/zenodo.22773411. Publisher record lists CC BY 4.0. | The demo shows two attributed images as resized browser previews. Source JPEGs and dataset archive are omitted. The video and report remain staged locally for team approval. [Dataset record](https://doi.org/10.5281/zenodo.22773411) · [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) |

## Demo image attribution and provenance

The organizer-facing demo answer should retain this attribution with the video. The pill previews are from **Tahir Mahmood, Pharmaceutical Tablet Defect Dataset v1.0 (PharmaVision), CC BY 4.0**, DOI 10.5281/zenodo.22773411. The previews were resized for the interface and captured in a captioned demonstration. The license applies to the source images. Team media and code terms are tracked separately.

The local PharmaVision RAR matched the Zenodo record MD5 `68bebce21636d5f15cedc406cc04d4d3`. The entries below were independently streamed from that RAR and matched the two demo fixture files byte-for-byte.

| Archive entry | SHA-256 |
|---|---|
| `PharmaVision/Test/normal/1.jpeg` | `cd4a94942a58886e7a2e1b5ba0381cf5c154b81e3d6332e42e48f5f29c785293` |
| `PharmaVision/Val/defective/1.jpeg` | `5cb131b6b18e66e5cc0e0be4581b015ae4359a4f51b8e479fe787007ebc8a39c` |
