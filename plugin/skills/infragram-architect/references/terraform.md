# Terraform and diagrams

Status: both directions ship, for AWS, Azure and Google Cloud. **A diagram
to Terraform** is the export's `terraform` format (section 1), and whether
it works, without deploying it, is `check:terraform`. **Terraform to a
diagram** is `import:terraform`, and a live estate to a diagram is
`discover:aws`, `discover:azure` and `discover:gcp`, read-only (section 3);
a live Kubernetes cluster is `discover:kubernetes`.

Two directions, one model in the middle:

```
a diagram  --(author, editor)-->  .infragram.json  --(export --formats terraform)-->  a Terraform skeleton
Terraform files, a plan, a state, a live account  --(import, discover)-->  a diagram file  --(compose)-->  HTML / SVG / PNG
```

The `.infragram.json` project is the only shape both directions share
([project-schema.md](project-schema.md)): elements with a provider, a
library icon, a caption; frames that contain them; connections between
them. Every rule below is about getting from that shape to Terraform without
inventing, and from Terraform into that shape without guessing.

## 1. A diagram to Terraform: the `terraform` export

Load this section when the user asks for Terraform, infrastructure as code,
modules, or "the code for this diagram". The export writes a *skeleton*,
honestly labelled: the resources the diagram asserts, placed the way its
frames contain them, with a variable wherever the diagram does not say.
Nobody has applied it.

### Command

```text
python "<skill>/scripts/infragram.py" export:project <project.infragram.json> --formats terraform
python "<skill>/scripts/infragram.py" compose <diagram.py> --formats html,svg,terraform
```

From Python, `diagram.export("dist", formats=("terraform",))`. `terraform`
goes with any other format and needs no browser. The exported editor page
carries both skeletons as well: its **Download** menu has *Terraform* and
*Terraform, registry modules*, each the folder as a `.zip`, written from the
diagram when the page was exported (an edit made in the page is not in
them, and the download says so). The skeleton is the folder
`<output-dir>/<slug>-terraform/`, laid out as below, written whole or not at
all; an existing folder is replaced when it is exactly what the last export
wrote, and otherwise only with `--force`. The command prints the folder, and
a note giving the number of variables to fill and of elements written as no
resource.

A diagram that draws nothing on AWS, Azure or Google Cloud is refused before
anything is written (exit 2): an empty skeleton would say nothing.

### The layout: modules and environments

Both formats write the layout HashiCorp's standard module structure and
style guide describe, the one a Terraform repository on GitHub has:

```text
<slug>-terraform/
├── README.md                 the layout, usage, what each thing became, what to fill
├── .gitignore
├── modules/                  one module a concern, holding what the diagram draws for it
│   ├── network/              main.tf  variables.tf  outputs.tf  versions.tf  README.md
│   ├── security/  secrets/  compute/  database/  storage/  loadbalancer/  monitoring/ ...
└── environments/
    ├── dev/                  main.tf  variables.tf  outputs.tf  locals.tf  providers.tf
    └── prod/                 versions.tf  backend.tf  terraform.tfvars.example
```

- **A module a concern**: `foundation` (Azure resource groups, Google
  APIs), `network`, `security`, `secrets`, `compute`, `containers`,
  `database`, `storage`, `messaging`, `analytics`, `loadbalancer`, `edge`,
  `dns`, `monitoring` -- only the ones the diagram fills. A diagram on
  several clouds has a folder a cloud (`modules/aws/network`,
  `modules/azure/network`). A module configures no provider: it declares
  the ones it needs, and the aliases it is handed.
- **Wired by the environment.** What one module reads of another is an
  output of the one and a variable of the other, and the environment passes
  it across: `vpc_id = module.network.vpc_id`. A module never names another
  module's resources.
- **Two environments.** `environments/dev` and `environments/prod` call
  every module once: the same code, each with its own `environment`, its
  own state (`backend.tf`, commented until you name the bucket) and its own
  `terraform.tfvars`. Work from one: `cd environments/dev`, `terraform init`,
  `terraform plan`.
- **Names from the diagram, as the style guide asks.** A block is named by
  what its caption says beyond what it is: "Public subnets" is
  `aws_subnet.public`, "Web servers" `aws_launch_template.web` and
  `aws_autoscaling_group.web`, a caption that only says what it is
  ("Application Load Balancer", "VPC 10.0.0.0/16") `main`; a component's
  security group is named for it (`aws_security_group.web`), a wire's rule
  for its two ends (`web_from_alb`). Variables and outputs are named the
  same way (`web_instance_type`, `public_subnet_ids`, `alb_dns_name`), in
  alphabetical order, a variable's type first.
- **READMEs**: the skeleton's says what it is, draws its layout, how to use
  an environment, what each element became and in which module, the values
  to fill, its modules and the environment's inputs and outputs, every wire
  and every element written as no resource; every module has its own, with
  its usage cut from the environment's call.

### Two styles: `terraform` and `terraform-modules`

`--formats terraform` writes plain resources in every module.
`--formats terraform-modules` writes `<slug>-terraform-modules/`, the same
layout, each module calling the public registry's maintained module where
one fits, at the version `assets/terraform/modules.json` pins
(`module "vpc" { source = "terraform-aws-modules/vpc/aws" ... }`), and plain
resources where none does. Both go together: `--formats
terraform,terraform-modules`. The wires are rules beside the groups they
open in both: AWS ingress rules (on the security group module's group in the
modules style), Azure network security rules, Google Cloud firewall rules
(the network module's `ingress_rules` in the modules style).

| What the diagram draws | Is written through |
|---|---|
| an AWS VPC frame, its zones, subnets and NAT or internet gateways | `terraform-aws-modules/vpc/aws`, the subnets in turn by zone (two a zone fit too) |
| an AWS component's own security group, a security-group frame | `terraform-aws-modules/security-group/aws` |
| an EC2 instance | `terraform-aws-modules/ec2-instance/aws` |
| several of one EC2 server, or one in an Auto Scaling group frame | `terraform-aws-modules/autoscaling/aws`, its launch template included |
| an RDS database (its subnet group included) | `terraform-aws-modules/rds/aws`; AWS keeps the master password |
| an Aurora cluster, its writer and subnet group | `terraform-aws-modules/rds-aurora/aws`; AWS keeps the master password |
| an ElastiCache (Valkey) replication group and its subnet group | `terraform-aws-modules/elasticache/aws` |
| an EFS file system and its mount target | `terraform-aws-modules/efs/aws`, with its policy refusing unencrypted transport and its backups on |
| an MSK cluster | `terraform-aws-modules/msk-kafka-cluster/aws` |
| a DynamoDB table | `terraform-aws-modules/dynamodb-table/aws` |
| an S3 bucket | `terraform-aws-modules/s3-bucket/aws`, public access blocked |
| an SQS queue, an SNS topic | `terraform-aws-modules/sqs/aws`, `terraform-aws-modules/sns/aws` |
| a VPC endpoint, a PrivateLink endpoint | `terraform-aws-modules/vpc/aws//modules/vpc-endpoints` |
| a Network Firewall | `terraform-aws-modules/network-firewall/aws//modules/firewall` |
| a site-to-site VPN's connection (its two gateways as resources) | `terraform-aws-modules/vpn-gateway/aws` |
| a transit gateway | `terraform-aws-modules/transit-gateway/aws`, not shared, no route table of its own |
| an ECR repository | `terraform-aws-modules/ecr/aws` |
| an ECS cluster, a Fargate service | `terraform-aws-modules/ecs/aws//modules/cluster`, `//modules/service` |
| an EKS cluster | `terraform-aws-modules/eks/aws`, its creator its admin, AWS's own encryption and logs |
| a Lambda function | `terraform-aws-modules/lambda/aws`, its role and log group included |
| a KMS key, a Secrets Manager secret | `terraform-aws-modules/kms/aws`, `terraform-aws-modules/secrets-manager/aws` (a random first value) |
| a CloudWatch log group | `terraform-aws-modules/cloudwatch/aws//modules/log-group` |
| an ACM certificate, an API Gateway HTTP API | `terraform-aws-modules/acm/aws` (its validation left to you), `terraform-aws-modules/apigateway-v2/aws` |
| an Application Load Balancer, its target groups and listeners from the wires | `terraform-aws-modules/alb/aws` |
| a Route 53 hosted zone | `terraform-aws-modules/route53/aws` |
| an Azure resource group frame | `Azure/avm-res-resources-resourcegroup/azurerm` |
| an Azure virtual network and its subnets | `Azure/avm-res-network-virtualnetwork/azurerm` |
| an Azure VM's network security group | `Azure/avm-res-network-networksecuritygroup/azurerm` |
| an AKS cluster frame (its default pool; the other pools as resources) | `Azure/avm-res-containerservice-managedcluster/azurerm` |
| an App Service and its plan | `Azure/avm-res-web-site/azurerm`, `Azure/avm-res-web-serverfarm/azurerm` |
| a storage account, a file share (with its account) | `Azure/avm-res-storage-storageaccount/azurerm` |
| a key vault, a managed identity | `Azure/avm-res-keyvault-vault/azurerm`, `Azure/avm-res-managedidentity-userassignedidentity/azurerm` |
| an Azure SQL database (its server included) | `Azure/avm-res-sql-server/azurerm` |
| a Cosmos DB account, an Azure Cache for Redis | `Azure/avm-res-documentdb-databaseaccount/azurerm`, `Azure/avm-res-cache-redis/azurerm` |
| a container registry | `Azure/avm-res-containerregistry-registry/azurerm` |
| a load balancer, a private endpoint | `Azure/avm-res-network-loadbalancer/azurerm`, `Azure/avm-res-network-privateendpoint/azurerm` |
| an Azure Firewall, a Bastion host (its public IP included) | `Azure/avm-res-network-azurefirewall/azurerm`, `Azure/avm-res-network-bastionhost/azurerm` |
| the public IP of an application gateway, a VPN gateway or a firewall | `Azure/avm-res-network-publicipaddress/azurerm` |
| a DNS zone, a private DNS resolver | `Azure/avm-res-network-dnszone/azurerm`, `Azure/avm-res-network-dnsresolver/azurerm` |
| Front Door, a DDoS protection plan, an ExpressRoute circuit | `Azure/avm-res-cdn-profile/azurerm`, `Azure/avm-res-network-ddosprotectionplan/azurerm`, `Azure/avm-res-network-expressroutecircuit/azurerm` |
| a Recovery Services vault, an Azure Virtual Desktop host pool | `Azure/avm-res-recoveryservices-vault/azurerm`, `Azure/avm-res-desktopvirtualization-hostpool/azurerm` |
| a Log Analytics workspace, Application Insights (on a workspace you name) | `Azure/avm-res-operationalinsights-workspace/azurerm`, `Azure/avm-res-insights-component/azurerm` |
| a Google Cloud VPC network, its subnetworks and firewall rules | `terraform-google-modules/network/google` |
| Cloud SQL for PostgreSQL | `terraform-google-modules/sql-db/google//modules/postgresql` |
| a Cloud Storage bucket, Memorystore for Redis | `terraform-google-modules/cloud-storage/google//modules/simple_bucket`, `terraform-google-modules/memorystore/google` |
| a Cloud Run service | `GoogleCloudPlatform/cloud-run/google//modules/v2` |
| Cloud NAT (its router included) | `terraform-google-modules/cloud-nat/google` |
| a Secret Manager secret, a Cloud Armor policy | `GoogleCloudPlatform/secret-manager/google`, `GoogleCloudPlatform/cloud-armor/google` |
| a load balancer's global address | `terraform-google-modules/address/google` |

#### What a module does beyond the plain resources

One rule on the three clouds, held by comparing what the two styles plan for
one of each component (`infragram.terraform.coverage`): where it decides
whether a skeleton **applies** in any region, **can be destroyed**, **can be
reached** or **works as drawn**, a module is called to do what the plain
resource does; what only **hardens** a resource, or is an operational
default of the module's authors, stays the module's. No module adds a
security group or KMS key the diagram does not draw (a component's own
security group is the security module's). The Azure Verified Modules are
called with `enable_telemetry = false`. The skeleton's `required_version`
is the strictest the modules it calls need (`>= 1.11.1` with the RDS or
Aurora module). What a module keeps only in a sensitive output (an Azure
SQL server's address, a Redis host, a Log Analytics workspace id) is a
sensitive output of its module and of the environment too. `google-beta` and
`azapi`, which the modules call beside `google` and `azurerm`, are configured
in each environment as those are and handed with them to a module on another
project or subscription.

| Cloud | Called to do what the plain resource does | Kept as the module has it |
|---|---|---|
| AWS | the security group module leaves the wires' ingress rules beside it be; EKS keeps a public endpoint; Network Firewall has no delete or subnet-change protection; a network in a second region takes that region's zones; RDS and Aurora keep their last snapshot under a name, so they destroy (the plain resources too) | EC2 requires IMDSv2; ECR tags are immutable; RDS, Aurora and ElastiCache encrypt at rest, ElastiCache in transit (clients use TLS); the ALB drops invalid headers; the VPC module takes over the default security group (no rules), route table and network ACL; EFS has a backup policy and refuses unencrypted transport; EKS logs its control plane (API, audit, authenticator) to a log group it manages for 90 days, creates its IAM role and OIDC provider, and installs no add-ons until you name them with your node groups (`addons`: vpc-cni, kube-proxy, coredns; the plain cluster installs the self-managed defaults, and neither runs a pod without nodes); Lambda creates its role and log group; ECS turns on Container Insights; MSK writes a broker configuration and autoscales storage; Secrets Manager gives a secret a random first value |
| Azure | public network access (storage, Key Vault, Cosmos DB, App Service, Log Analytics); no availability zones (public IPs, load balancer, Firewall, Bastion, container registry, Cosmos DB); one App Service worker, not zone-balanced; Cosmos DB's session consistency | storage turns shared keys and blob public access off (Entra ID authentication, TLS 1.2); Key Vault authorizes by RBAC with purge protection; Cosmos DB turns key authentication off and backs up continuously for 30 days; App Service allows FTPS only and stays always on; the container registry keeps untagged images 7 days; the Recovery Services vault restores across regions, with soft delete; Application Insights caps ingestion at 100 GB a day and needs a Log Analytics workspace you name |
| Google Cloud | the APIs a module could turn on are the foundation's (`project_services`) | Memorystore requires TLS from its clients; Cloud Storage versions objects; Cloud SQL creates a default database and a user with a random password; Cloud Run creates its own service account; Cloud SQL and Cloud Run are protected from deletion, as the plain resources are by the provider's default |

A log group a module manages (Lambda's, EKS's control plane's) is a
CloudWatch card beside its component when the skeleton is imported back.

Written as plain resources, for want of a module that fits: AWS Direct
Connect, Shield, Glacier, Athena, Transfer Family, GuardDuty, Security Hub,
Macie, CloudTrail and Config; an Azure virtual machine (its network security
group is a module), VM scale sets, AKS node pools past the first, an
application gateway or VPN gateway (their public IPs are modules), Data
Explorer, Stream Analytics, IoT Hub, Digital Twins, Defender, Policy and
Sentinel; a Compute Engine instance and a GKE cluster (the module needs a
network and a subnetwork the diagram may not draw).

### What it writes

| Path | Holds |
|---|---|
| `modules/<concern>/main.tf` | the concern's resources, or the registry modules' calls, in the order the diagram draws them, each after a comment naming its element |
| `modules/<concern>/variables.tf`, `outputs.tf` | what the module reads (`name`, `tags`, another module's ids, the values to fill) and what others read of it |
| `modules/<concern>/versions.tf` | the providers it needs, and the aliases it is handed |
| `environments/<env>/versions.tf` | `required_version` (the strictest its modules need) and each provider pinned (`hashicorp/aws ~> 6.0`, `hashicorp/azurerm ~> 4.0`, `hashicorp/google ~> 7.0`) |
| `environments/<env>/backend.tf` | where the environment keeps its state: commented until you name the bucket, the key its own |
| `environments/<env>/providers.tf` | one provider configuration per AWS region, Azure subscription or Google Cloud project the frames name; AWS sets `default_tags` |
| `environments/<env>/variables.tf`, `locals.tf` | every input, typed and described; `name` (`<project>-<environment>`), the tag map or Google Cloud's labels, and the two zones a tier spreads across |
| `environments/<env>/main.tf` | one call of each module, in order: foundation, network, security, then what runs on it, keeps its data and reaches it |
| `environments/<env>/outputs.tf` | every network and subnet id and every component endpoint |
| `environments/<env>/terraform.tfvars.example` | every value the diagram does not answer, as a placeholder to fill |

### How a diagram becomes resources

- **Frames.** A frame's kind decides what it is to Terraform. An
  organization, account or folder is the credentials' business (a note). A
  **region** frame is a provider configuration: a region variable, and on
  AWS an alias per further region; an Azure **subscription** is a provider
  alias; a Google Cloud **project** frame gives the project id. An Azure
  **resource group** is a resource that everything inside it names. A
  **network** frame (VPC, VNet, VPC network) is the network; a **subnet**
  frame is a subnet in it, public or private by its kind. An AWS subnet
  frame drawn in no **availability zone** frame is a tier: a subnet in each
  of two zones (`count = length(var.azs)`), which a load balancer and a
  database subnet group need, its ranges the caption's halved or carved in
  order from the VPC's (`10.0.0.0/24`, `10.0.1.0/24` for the first tier); a
  subnet in a zone frame is that zone's. A **security group** frame is a
  group its members wear. A **cluster** frame (AKS, GKE) is the cluster,
  its first node pool drawn in it the default pool. An **Auto Scaling
  group** frame makes the servers in it a group.
- **Components.** Each component the provider's table knows becomes its
  resources, in its concern's module. The tables cover the common services
  of each cloud: compute, networking and gateways, databases and caches,
  storage, queues, containers and Kubernetes, keys and secrets, edge,
  logging. A component the table does not know is listed in the README, with
  the reason.
- **What the card says.** A server the card counts several of (its sizing,
  "3 x m6i.large", "Auto Scaling") is an Auto Scaling group from a launch
  template, its desired, least and most counts variables with the card's
  count as their default. An instance type or class the sizing or detail
  names (`.sizing(instance_type="m6i.large")`, "db.r6g.large"), and
  "Multi-AZ", are the defaults of their variables. A bucket keeps its
  versions.
- **Wires.** A wire becomes a rule that lets its traffic in, on the three
  clouds:
  - **AWS.** Each component in a VPC wears a security group of its own. A
    wire between two of them is an ingress rule on the target, from the
    source's group; a wire from users or the internet to a component in a
    public subnet is a rule from `0.0.0.0/0`. A load balancer's wires
    become its target groups, attachments (an Auto Scaling group's through
    `aws_autoscaling_attachment`) and listeners; a listener on 443 asks
    for a certificate.
  - **Azure.** Each virtual machine wears a network security group on its
    interface and an application security group of its own. A wire to it
    is an inbound rule on its group, from the source machine's application
    security group, from the range of the subnet any other source sits in,
    or from `Internet`, each rule at the group's next priority.
  - **Google Cloud.** Each Compute Engine instance wears a network tag. A
    wire to it is an ingress firewall rule to that tag, from the source
    instance's tag, from the range of the subnetwork any other source sits
    in, or from `0.0.0.0/0`; an instance the internet reaches gets an
    external address.

  The port is the number in the label (`HTTP :8080`), every one of them on
  Azure and Google Cloud, ranges too (`TCP 8000-8080`), else the port its
  word names (`HTTPS` 443, `postgres` 5432, `redis` 6379), else the
  target's own port (a PostgreSQL RDS listens on 5432), else a variable to
  fill. The README says how every wire was taken, and why one was not.
- **Names in the cloud and values.** Every resource's name in the cloud is
  `<name>-<its element's name>` (`aws-three-tier-prod-web`), cut to the
  provider's rules. An address range comes from its frame's caption
  (`VPC 10.0.0.0/16`), an AWS region from its region frame's caption
  (`us-east-1`), a Google Cloud project id from its project frame's.
  Whatever else the diagram does not say is a variable: with a default
  where one is sensible (`t3.micro`, `POSTGRES_16`), else one to fill (an
  AMI, a domain name, a certificate).
- **What a frame implies.** An AWS VPC with public subnets and no internet
  gateway drawn in it gets one, with the route table that makes those
  subnets public; the README notes it. The Google APIs the resources need
  are the foundation module's, and every other Google module waits for it.
- **A pipeline's sign-in.** A wire from GitHub (its repository, Actions,
  runner, OIDC token or the token's issuer) into a cloud identity is a
  trust in GitHub's OIDC issuer for the diagram's repository and the
  approval gate's environment, with no secret. On AWS it is an IAM role's
  trust policy; on Google Cloud, a Workload Identity pool. On Azure it is
  either a user-assigned managed identity's federated credential, or
  (through the `azuread` provider, declared only where it is used) an
  **App registration**'s federated credential, whose **Enterprise
  application** wired from it is written as its service principal. The
  identity's wires to what it deploys grant what each target needs and no
  more: an AWS policy on those resources, Azure role assignments (to the
  service principal, never the app registration), Google project roles.
  `examples/*_github_actions_oidc.py` show each.
- **Not written.** People and clients, elements outside the three clouds,
  shared components with no cloud resource, and components drawn where
  their resources cannot go (a load balancer outside any network) are
  listed in the README, each with its reason.

### Whether it works, without deploying it: `check:terraform`

```text
python "<skill>/scripts/infragram.py" check:terraform <project.infragram.json | diagram.py | page.html | folder>... [--style resources|modules] [--var-file mine.tfvars] [--output-dir dist] [--keep DIR] [--fetch]
```

Terraform itself reads each skeleton, in a copy (the folder given is never
written): `terraform fmt -check`, then `terraform init -backend=false` and
`terraform validate` offline, then a plan against mocked providers
(`terraform test`, a `mock_provider` for every provider the configuration or
its modules use, but `random`, `time`, `null`, `local`, `cloudinit` and
`archive`, which work on the machine and reach nothing). `external` is mocked
too, so a data source's program never runs (its result is empty), and so is
`tls`, whose `tls_certificate` would fetch a URL. Nothing is created, nothing
is run, no cloud is called and no credentials are read. A diagram (a document, a diagram file, or an exported page: the
diagram it was exported from) is checked in both styles, or the one
`--style` names; a Terraform folder as it is, edits and all; a folder of
them (an export's output folder) one by one.

- **Offline.** The providers come from the plugin folder (`--plugin-dir`,
  else `TF_PLUGIN_CACHE_DIR`, else the Terraform CLI configuration's
  `plugin_cache_dir`, else Infragram's cache), the registry modules from the
  module cache, copied into the checked copy and called there by path.
  `--fetch` downloads, once, the registry modules the export pins and the
  providers they and the clouds need, into both. What neither holds is
  named, and that configuration is not checked. `--fetch` is the one step
  that reaches the network: offer it when a `SKIP` names a missing module or
  provider, and run it only when the user agrees.
- **Values.** A variable nothing gives a value gets a made-up one of the
  shape its name and type ask for (an ARN, a CIDR, an SSH public key, a list
  of one...), and the command names each. The configuration's own
  `terraform.tfvars` and `*.auto.tfvars`, `--var-file`, `--var` and
  `TF_VAR_` variables are the plan's.
- **What it says.** A line a configuration: `PASS` with what the plan would
  create, `FAIL` with the step Terraform refused and its words, or `SKIP`
  with what was missing. Each plan, as Terraform prints it, is written to
  `<output-dir>/<folder>.plan.txt`. `--keep DIR` keeps the checked copies,
  with the modules copied in, the made-up values
  (`infragram-check.tfvars.json`) and the mocked test
  (`tests/infragram-check.tftest.hcl`). Exit 0 when every configuration is
  planned, 1 when Terraform refused one, 2 when one could not be checked or
  a source could not be read.

It needs the Terraform CLI, 1.7 or later for the plan (an older one
validates only). A configuration that reads `terraform_remote_state` is
validated but not planned: no mock answers it, and a plan would read that
state from its backend. A plan against mocked providers shows the
configuration is valid, that its modules' own rules hold for the values
given, and what it would create. It cannot show that the cloud accepts it
(quotas, a name already taken, permissions, a region without the service):
that is a real `terraform plan`, signed in, which only the user runs.

### What a reviewer would stop: `check:policy`

```bash
infragram check:policy diagram.py plan.infragram.json ./infra --strict
```

`--json` prints what was read and found as one JSON document (each finding
with its rule, severity, and the element or the resource, file and line) and
nothing else on standard output, for a CI job to read.

A diagram (a document, a diagram file, or a page or picture carrying its
document) is read against four rules, whether it was drawn by hand or
imported. An imported security group rule that lets the internet in is a
wire from the Internet card, so the rules read those wires too:

- `database-in-public-subnet`: a database inside a public subnet frame.
- `internet-reaches-database`: a wire from the internet straight to a
  database.
- `internet-reaches-private-subnet`: a wire from the internet to something
  in a private subnet that is no front door. A load balancer, gateway,
  firewall or WAF (a networking or security component) is there to be
  reached.
- `admin-port-open-to-internet`: a wire from the internet that lets in SSH
  (22), RDP (3389) or every port. Every port is an error; the rest are
  warnings.

A Terraform folder goes to Checkov or Trivy, the first on the PATH, or the
one `--scanner` names. They are the user's own: nothing installs them, and a
folder is skipped, not failed, when neither is there. Findings print as
`POLICY` lines, and they fail the command (exit 1) only with `--strict`.
Checkov flags much of a skeleton Infragram writes (no encryption key, no
logging), because that is where the code starts. No shipped template or
example breaks a diagram rule.

### Before you deliver

- Say it is a skeleton: fill `terraform.tfvars` from the example, read every
  resource, then run `terraform init`, `terraform validate` and
  `terraform plan`. Never run `terraform apply` for the user. To show that
  it works without deploying it, run `check:terraform`: Terraform on a
  copy, offline, against mocked providers.
- Report the folder, the variables left to fill and the elements written as
  no resource, from its README.
- When the user needs a component the README lists as having no Terraform
  mapping, say so; do not hand-write resources into the skeleton unasked.

## 2. Writing Terraform for a cloud, linearly

The export (section 1) writes Terraform in this order, and so does an agent
writing it by hand, without skipping ahead. Each step's output is the next
step's input, so a diagram of the result is a matter of reading the files in
the same order.

1. **Scope in one paragraph.** Provider, region(s), environment name,
   what must exist at the end (the components of the diagram, if there is
   one). No resources yet.
2. **Backend and providers.** Each environment's `versions.tf` pins
   `terraform` and every provider, its `backend.tf` names its state store,
   its `providers.tf` configures them: one provider alias per region or
   account used. A module configures none.
3. **Variables and locals.** `variables.tf` holds every input with a type
   and a description, in alphabetical order; `locals.tf` derives the name
   (`"${var.project}-${var.environment}"`) and the tag map, which every
   module takes as `name` and `tags`. Nothing else is named ad hoc.
4. **The boundary frames first.** Account/project/resource group, then
   region, then network (VPC / VNet / VPC network), then subnets and
   availability zones. These are the frames of the diagram, and they are
   created before anything that sits inside them.
5. **Security.** Security groups / NSGs / firewall rules, IAM roles and
   service accounts, key rings. Written before compute so compute can
   reference them, never the other way round.
6. **Data and storage.** Databases, caches, object storage, queues,
   volumes.
7. **Compute and platform.** Instances, node pools, clusters, functions,
   containers -- each referencing the subnet, security group, role and
   data endpoints already declared.
8. **Edge and traffic.** Load balancers, gateways, DNS records, CDN,
   certificates -- the last things created, the first things a user meets.
9. **Observability.** Log sinks, metrics, alerts, dashboards.
10. **Outputs.** `outputs.tf` exposes every endpoint another module or a
    reader needs; the diagram's captions come from these names.
11. **Validate.** `terraform fmt -check`, `terraform validate`, and a
    `terraform plan` whose resource count equals the number of components
    the scope paragraph promised.

One module a concern under `modules/` (`network`, `security`, `compute`,
`database`, `storage`, `loadbalancer`, `monitoring`), each its own `main.tf`,
`variables.tf`, `outputs.tf` and `versions.tf`, and one composition an
environment under `environments/` calling each once. A module takes what
it reads of another as a variable (`vpc_id`, `private_subnet_ids`) and the
frame it lives in as inputs (`resource_group_name`, an address range), so
the containment is explicit in the call, not inferred.

Provider notes that change the order:

| Provider | Frame resources (step 4) | What must come first |
|---|---|---|
| AWS | `aws_organizations_account`, `aws_vpc`, `aws_subnet`, availability zone by `availability_zone` | IAM roles before EKS/ECS; route tables and IGW/NAT before anything private reaches out |
| Azure | `azurerm_resource_group`, `azurerm_virtual_network`, `azurerm_subnet` | Resource group before all; NSG associated to subnet before NICs |
| Google Cloud | `google_project`, `google_compute_network`, `google_compute_subnetwork` | APIs enabled (`google_project_service`) before any resource of that API |
| DigitalOcean / Hetzner / Vultr / Linode | project + VPC | Firewall before droplets/servers reference it |
| Kubernetes / OpenStack / vSphere / Proxmox | namespace / project / datacenter / node | The platform frame first; on-prem hosts are data sources, not resources |

## 3. What exists, to a diagram: `import:terraform` and `discover:<cloud>`

Load this section when the user asks for a diagram of infrastructure that
already exists: their Terraform, a plan or a state, or what is running in an
account ("diagram our Terraform", "draw what is in this subscription"). The
import writes a **diagram file** (Python, the form `compose` runs, see
[compose.md](compose.md)) and a **report**, then draws the file like any
other. The file is where the diagram starts: the user regroups, recaptions
or removes what they like and composes it again.

### Commands

```text
python "<skill>/scripts/infragram.py" import:terraform <folder> [--var-file prod.tfvars] [--var name=value]
python "<skill>/scripts/infragram.py" import:terraform <plan.json | terraform.tfstate>
python "<skill>/scripts/infragram.py" discover:aws --region eu-west-1 [--region ...] [--profile P]
python "<skill>/scripts/infragram.py" discover:azure [--subscription S] [--resource-group G ...] [--source resource-graph]
python "<skill>/scripts/infragram.py" discover:gcp [--project P] [--region R ...]
python "<skill>/scripts/infragram.py" discover:kubernetes [--context C] [--namespace N ...] [--include-system]
```

Each takes `--title`, `--spec <file.py>` (default `<output-dir>/<slug>.py`),
`--no-export` (the diagram file and report only), and every option of
`compose` (`--formats`, `--output-dir`, `--verify`, `--force`, ...). It
prints `READ` (what was read), `SPEC` (the diagram file), `REPORT`
(`<slug>.import.md`), then what `compose` prints. An existing diagram file
or report is replaced when it is exactly what the last import wrote; one
edited by hand is refused unless `--force` is given, so the edit is not lost; an estate with nothing on AWS,
Azure or Google Cloud is refused (exit 2).

**A plan draws its changes.** Imported from `terraform show -json plan.out`,
every card carries what the plan does to it, written into the diagram file
as `.change("create")` (or `update`, `replace`, `delete`): the card is
outlined and tinted in the action's colour (green added, amber changed,
purple replaced, red destroyed), its detail line starts with the mark and
word (`+ added`, `~ changed`, `± replaced`, `− destroyed`), which the icon
look keeps too, and the band above the drawing gives the plan's count the way
`terraform plan` ends (`Plan: 2 to add, 1 to change, 1 to destroy`). A
resource the plan destroys is read from `prior_state` and drawn, marked
destroyed. A card drawn from several resources takes one action: all added
is added, all destroyed is destroyed, a replace anywhere is a replace, any
other mix is changed. A state or a configuration marks nothing.

**Drift.** `terraform plan -refresh-only -out=drift.out`, then
`terraform show -json drift.out > drift.json`, and `import:terraform drift.json`
marks every resource changed outside Terraform `≈ drifted`, in blue, with
`Plan: 2 drifted` above the drawing. Terraform reads the account; Infragram
only reads the JSON. In an ordinary plan a drifted resource the plan also
acts on shows the planned action, which is what an apply does.

**Two versions.** `infragram diff before after` compares any two diagrams (two discovery runs, two commits of a document, a design and what was imported), matched by element id, and draws the second with the same marks, what was removed drawn back in; `--report-only` just lists it. `--json` prints the change report as one JSON document, `--comment FILE` writes it as Markdown for a pull request, and `--exit-code` exits 1 when the two differ (0 when they are the same, 2 on an error), as `git diff --exit-code` does.

**On every pull request.** `--comment FILE` writes the plan's changes as Markdown (and `import:diagram --comment` what a draw.io or Mermaid file was drawn as, with the guesses to check) (the count, then each resource by action with what it is drawn as) for a pull request comment. [`../assets/ci/terraform-plan-diagram.yml`](../assets/ci/terraform-plan-diagram.yml) is a workflow Forgejo Actions and GitHub Actions both run as it is: it plans, draws the plan, uploads the picture, page and diagram file, puts the comment in the job summary, and on GitHub posts it on the pull request. It never applies.

**Corrections that survive a re-import.** Rather than editing an imported diagram file (which the next import refuses to replace, or with `--force` loses), keep corrections in `<diagram>.overrides.toml` beside it: `[[remove]]` by `address`, `[[relabel]]` with `caption` and `detail`, `[[connect]]` and `[[disconnect]]` with `from` and `to` (and `label`, `dashed`), addresses with shell wildcards. Every import applies them and names any rule that no longer matches what it drew.

**What each reads.**

- A **folder** is a configuration's root module, read as Terraform resolves
  it: variables from their defaults, then `terraform.tfvars`,
  `*.auto.tfvars`, `--var-file` and `--var`; locals evaluated, `for`
  expressions and the common functions included; `count` and `for_each`
  over known values expanded to their instances, and `dynamic` blocks to
  their blocks; modules with a local `source` read too, one per `for_each`
  key. A module from a registry or git is read too when `terraform init`
  has installed it in the folder (`.terraform/modules`), or when
  infragram's module cache holds it at a version the call allows; any other
  is named in the report, and a plan or a state shows what it holds.
  `azapi_resource`s (the Azure Verified Modules write networks with them)
  are drawn as the Azure resources they are. Nothing is run.
- A **plan** (`terraform plan -out plan.out` then `terraform show -json
  plan.out > plan.json`) is the truth for what will exist, registry modules
  included; a **state** (`terraform show -json > state.json`, or the
  `terraform.tfstate` file itself) for what does. The user makes these;
  the import never runs `terraform`.
- **`discover:<cloud>`** reads through `aws`, `az` or `gcloud` as the user is
  already signed in, with `describe`, `get`, `list` and `show` calls only:
  nothing is created, changed or deleted. A call the account may not make is
  a note in the report, and the rest is still drawn. An AWS default VPC
  nobody uses is left out.
- **`discover:azure --source resource-graph`** reads the same subscription in
  one paged Azure Resource Graph query through `az rest` (no CLI extension,
  the same Reader role) instead of a list call per kind of resource and per
  network and SQL server. The rows are handed to the same reader, flattened
  the way the CLI prints them, so the diagram file, report and drawing are
  the same; the report notes how it was read. Azure only: the other clouds
  read through their list calls.

### A Kubernetes cluster: `discover:kubernetes`

It reads through `kubectl` as the kubeconfig signs in, and only reads:
`config view --minify`, then one `get <kind> -o json` per kind (ingresses,
services, deployments, statefulsets, daemonsets, cronjobs, jobs,
replicasets, pods, horizontal pod autoscalers, persistent volume claims).
A kind the account may not list becomes a note, and the rest is still
drawn. A cluster is drawn as it is, not through Terraform's terms:

- **Frames.** The cluster frame holds a frame per namespace. Each Service's
  app is a workload frame read left to right: the Service, the workloads its
  selector matches, what autoscales them, and the claims only they mount.
  The Ingress and whatever no Service selects (a CronJob, a bare Pod) stand
  in the namespace.
- **Folded.** What a controller made is folded into it: a Deployment's
  ReplicaSets and Pods, a CronJob's Jobs and their Pods, a DaemonSet's
  Pods, and a StatefulSet's Pods and the claims its volume claim templates
  made (`<template>-<set>-<n>`, counted on the card). The report lists each
  one and what it went into.
- **Wires**, each read from the objects themselves: an Ingress to the
  Services its rules and default backend name (labelled host and path), a
  Service to the workloads its selector matches (labelled with the target
  ports), a workload to the claims its pod template mounts, and an
  autoscaler to its scale target (dashed, `scales`).
- **Left out.** `kube-system`, `kube-public` and `kube-node-lease`
  (`--include-system` draws them), and the API server's own `kubernetes`
  Service in `default`.

Every card's popup carries `Resource` (`Kind/namespace/name`), the kind,
the namespace and its images. Overrides address a card by that name.

### How it is drawn

- **Frames.** Networks, subnets, resource groups and clusters are frames,
  inside the place they are in: AWS Cloud, region, availability zone; an
  Azure subscription and location; a Google Cloud project. A subnet is
  public when it maps public addresses or routes to an internet gateway.
- **Components** sit in the deepest frame they name: directly (`subnet_id`),
  or through a helper they use (an instance's security group names its VPC,
  a database's subnet group its subnets, a VM's network interface its
  subnet). Each component carries a popup table: the resource it was drawn
  from, where it was read, and its main attributes.
- **Wires** come from what the resources say about traffic: an AWS security
  group rule, from what wears the source group (or the internet) to what
  wears the target group, labelled with its port (`HTTPS :443`); an Azure
  network security group's inbound rule, from the internet, a range or an
  application security group to what the group guards on its subnets and
  network interfaces (a group on a subnet is also a badge on the subnet's
  corner, below); a Google Cloud firewall rule, from the internet, a
  range, tags or service accounts to the instances its targets name; a load
  balancer to its targets; a resource that is only a wire (a DNS alias, a
  subscription, an event source mapping); and any other argument of one
  drawn resource that names another. A rule that says anything inside may
  pass (`VirtualNetwork`, a range holding its own targets' subnet), a deny,
  an outbound rule and a ping draw nothing. A resource joined to a network
  (a transit gateway's attachment) says so in its popup, and two networks
  joined (a peering) get a card in the first.
- **What applies to an Azure subnet** is a badge on the subnet's top-right
  corner, where Azure's reference diagrams seat it: its network security
  group on the corner point, its route table beside it, each named by the
  resource; one group or table on two subnets is on each. A group on a
  network interface alone is drawn only as the wires it allows, the way the
  Terraform export writes a machine's rules back. The diagram file writes a
  badge as `.badge(azure.NetworkSecurityGroups, label="nsg-web")` on the
  subnet's `with` line.
- **Names.** A resource's `Name` tag or `name`, else its name in the
  configuration; a prefix every name shares (`shop-prod-`) is left out of the
  captions.
- **Folded and left out.** A helper is folded into what it belongs to (a
  listener into its load balancer, a DNS record into its zone); identity,
  policy and configuration (IAM, keys' aliases, an AWS route table) and other
  providers are left out; a type the tables do not know yet is drawn as its
  provider's generic component, captioned with the type. The report lists
  every resource and where it went.

### From VS Code

In VS Code the plugin's `/infragram-architect:import` and
`/infragram-architect:discover` commands run these for you. Without them, a
task runs them from the Command Palette (*Tasks: Run
Task*); put this in the workspace's `.vscode/tasks.json`, with `<skill>` the
skill's folder:

```json
{
  "version": "2.0.0",
  "tasks": [
    {
      "label": "Infragram: diagram of this Terraform",
      "type": "shell",
      "command": "python",
      "args": ["<skill>/scripts/infragram.py", "import:terraform", "${workspaceFolder}",
               "--output-dir", "${workspaceFolder}/diagrams", "--force", "--verify"],
      "problemMatcher": []
    }
  ]
}
```

### Before you deliver

- Report the `READ`, `SPEC` and `REPORT` lines, every file written, the
  verification verdict, and the notes: what was not read, and why.
- Say what the report counts as left out or drawn generically, so the user
  knows the picture's limits.
- Never run `terraform apply`, `plan` or `init` for the user on their
  configuration (`check:terraform` runs them on a copy, offline, against
  mocked providers), and never a cloud command that changes anything.

## 4. What exists

- The `terraform` export format: a diagram's skeleton for AWS, Azure and
  Google Cloud as a module a concern and two environments (section 1), and
  `terraform-modules`: the same layout through the public registry's
  modules where one fits.
- `check:terraform`: whether a diagram's skeletons, or a Terraform folder,
  work, without deploying them: Terraform offline and a plan against mocked
  providers (section 1), with the plugin's `check-terraform` command.
- `import:terraform` and `discover:aws|azure|gcp`: an existing estate as a
  diagram file, a report and the exported diagram (section 3), with the
  plugin's `import` and `discover` commands.
- The project schema, node classes for nineteen libraries, frames per
  library, the composer and the checkers: the middle of the pipeline.
- Terraform-related *icons* (`onprem.iac.Terraform`, the DevOps
  primitives), for drawing a pipeline that runs Terraform.
