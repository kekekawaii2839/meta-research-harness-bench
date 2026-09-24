# Task: Explain SSA's feature alignment method for regression TTA

Write an original 450–650 word technical exposition for a reader familiar with regression and PCA. Explain the stated motivation and method, and instantiate the discussion with the fixed UTKFace setting. Use original prose, cite the claim IDs inline, and do not report performance results. The task is exposition, not independent verification of method efficacy.

## Fixed scientific specification

The TTA setting uses an unlabeled target dataset T; source data S are inaccessible during adaptation and target labels are unavailable. The assumed covariate shift is p_s(x) != p_t(x) while p_s(y|x)=p_t(y|x). [C1]

Write the regressor as f_theta(x)=h_psi(g_phi(x)), z=g_phi(x) in R^D, with scalar linear head h_psi(z)=w^T z+b. Given source features z_i^s, define mu^s=(1/N_s) sum_i z_i^s and Sigma^s=(1/N_s) sum_i (z_i^s-mu^s)(z_i^s-mu^s)^T (population divisor). PCA gives unit eigenvectors v_d^s and eigenvalues lambda_d^s; retain the K largest eigenvalues lambda_1^s > ... > lambda_K^s and their eigenvectors. Define V^s=[v_1^s,...,v_K^s]^T in R^(K x D). [C2]

The head's sensitivity along a retained direction motivates alpha_d=1+|w^T v_d^s|. For target minibatch features z_i^t=g_phi(x_i^t), project as z_tilde_i^t=V^s(z_i^t-mu^s). The projected target minibatch has coordinate means mu_tilde_d^t and variances sigma_tilde_d^(t 2), computed using the population divisor B. The projected source moments are 0 and lambda_d^s, respectively; these are moments of projected features, not a claim about normalization-layer statistics. [C3, C4]

The complete SSA loss is the weighted sum of BOTH directed KL divergences per retained coordinate:

L_TTA(phi)=sum_(d=1)^K alpha_d { D_KL(N(0,lambda_d^s) || N(mu_tilde_d^t,sigma_tilde_d^(t 2))) + D_KL(N(mu_tilde_d^t,sigma_tilde_d^(t 2)) || N(0,lambda_d^s)) }.

For positive variances, D_KL(N(m1,s1^2)||N(m2,s2^2))=log(s2/s1)+(s1^2+(m1-m2)^2)/(2s2^2)-1/2. Do not characterize this as one-way KL. During TTA the paper states that only normalization-layer affine parameters gamma and beta are updated, with other feature-extractor parameters frozen. The paper does not specify handling of zero variance in the displayed Gaussian KL formula. [C4, C5]

For UTKFace, the task is age prediction; the source model is trained on original images and target evaluation uses 13 ImageNet-C corruption types at the highest of five severity levels (severity 5). The backbone is ResNet-50, penultimate features have D=2048, and default K=100. [C6]

## Claim IDs and source evidence

All claims cite ssa-paper-v1, SHA256 77cbdd9cbe5498f49625dc0c0c269c3d85a8bc18707f581d6ed1b2783c8dad60.

- [C1] Section 2, paragraph S2.p1: unlabeled target data, no source access/target labels, covariate shift conditions; Section 3.2 paragraphs S3.SS2.p1–p3: motivation and subspace significance.
- [C2] Eqs. (1),(5), HTML ids S3.E1/S3.E5 and Section 3.2 paragraph S3.SS2.p2 (source mean, covariance, PCA/eigenvalues).
- [C3] Eq. (6), HTML id S3.E6 and paragraph S3.SS2.p4 (linear regressor and weighting).
- [C4] Section 3.2 paragraph S3.SS2.p5 and complete equation group S3.EGx4, including all continuation rows for Eq. (8), HTML ids S3.E8 and adjacent equation rows; target projection, projected moments, zero projected source mean, eigenvalue variances, and both KL directions. Target batch moments also defined by Eqs. (1),(2), ids S3.E1/S3.E2 and S3.SS1.p3.
- [C5] Section 3.2 paragraph S3.SS2.p6 (only normalization affine gamma/beta updated; other feature extractor parameters frozen). These normalization-layer moments are distinct concepts from the K-dimensional projected-feature moments in [C4].
- [C6] Section 4.1 paragraph S4.SS1.p3 (UTKFace task, source original images, 13 ImageNet-C corruption types, highest severity); Section 4.2 paragraphs S4.SS2.p1 (ResNet-50), p2 (D=2048, K=100).

## Required headings

Motivation and setup; Subspace detection; Dimension weighting and alignment; Normalization and UTKFace; Limits.

Preserve the population covariance convention, ordered PCA basis, symmetric two-way KL, and positive-variance limitation. Do not invent optimizer details, describe unspecified behavior as fact, or imply projected-feature moments are BN moments. Cite claims by ID and give enough locator information for a reader to find the source evidence.

