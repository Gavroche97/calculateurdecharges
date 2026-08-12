import streamlit as st
import pandas as pd
import plotly.express as px
import psutil

#A faire
# - Intégrer calcul de l'ECS dans le chauffage
#    - Prendre en compte la perte lié à l'eau chaude qui circule en boucle dans le réseau
#    - Corriger le calcul
#0.4 à 0.8 : Très bien isolé (RT2012 / BBC) - 0.9 à 1.1 : Isolation standard (Années 90/2000) - 1.2 à 1.6 : Mal isolé (Passoire thermique).
#Mododèle Herz Firematic 120 d'une capacité de 120kW
#Modèle Atlantic Varmax 2 140 d'une capacité de 140kW

# Commande pour 
st.set_page_config(
    page_title="Calculateur de Charges",
    page_icon="logoResidence.png",
    layout="wide"  # Force l'affichage sur toute la largeur de l'écran
)
###################################################
# Classe de Calculateur de charges de copropriété #
###################################################
class Chaudiere:
    def __init__(self,Label, IDPrestation, 
            NomUnite,PrixUnite,kWhUnite, 
            ProductionMaxkW,description=None,seuilFonctionnement=None,seuilDureeActivation=None):
        self.Nom=Label
        self.IDPrestation=IDPrestation

        self.NomUniteCombustible=NomUnite
        self.PrixUniteCombustible=PrixUnite
        self.kWhUniteCombustible=kWhUnite

        self.PrixkWh= PrixUnite/kWhUnite
        self.ProductionMaxkW=ProductionMaxkW
        self.OrdreUtilisation=0
        self.Description=description
        self.SeuilFonctionnementPct=seuilFonctionnement
        self.SeuilDureeActivationMn=seuilDureeActivation

        self.PuissanceUtiliseeEauChaudekWh=0
        self.PuissanceUtiliseeChauffagekWh=0

        self.PicProductionkW=0
        self.CreuxProductionkW=0

class Residence:
    def __init__(self,Label, VolumeTotalAChauffer, CoefficientIsolation,DfTantiemes):
        self.Nom=Label
        self.VolumeTotalAChaufferM3=VolumeTotalAChauffer
        self.CoefficientIsolation=CoefficientIsolation
        self.DfTantiemes=DfTantiemes

class Prestation:
    """
    Classe d'objet permettant de définir une prestation de copropriété avec son nom et son coût associé.
    """
    def __init__(self, Nom, Cout,Description,Prestataire,IDPrestation=None, TopPrestationChoisie=False):
        self.Nom = Nom
        self.Cout = Cout
        self.Description = Description
        self.IDPrestation = IDPrestation
        self.Prestataire=Prestataire
        self.TopPrestationChoisie = TopPrestationChoisie

class Provision:
    """
    Classe d'objet permettant de définir une provision de copropriété avec son nom et son montant associé.
    """ 
    def __init__(self, Nom, Provision,Description,IDPrestation,IDTantiemes,descriptionLongue):
        self.Nom = Nom 
        self.Provision = Provision 
        self.Description = Description
        self.IDPrestation = IDPrestation
        self.IDTantiemes = IDTantiemes
        self.DescriptionLongue = descriptionLongue

class CalculateurDeCharges:
    """
    Classe d'objet permettant de calculer les charges de copropriété en fonction des lots, des prestations et des provisions.
    """
    def __init__(self,LstLot,
                LstProvisions: list[Provision], 
                LaResidence:Residence,
                LstChaudieres:list[Chaudiere]):

        #Initialiser les attributs de la classe
        self.LotsDontOnVeutCalculerLesCharges = LstLot 
        self.CaracteristiquesDeLaResidence=LaResidence
        self.ChaudieresDeLaResidence=sorted(LstChaudieres, key=lambda chaudiere: (chaudiere.OrdreUtilisation if chaudiere.PrixkWh is not None else 999))

        self.TemperatureLot = 1
        self.TemperatureExterieure = 1
        self.TemperatureResidence=1

        #Créer un dico pour initialiser le tableau des tantièmes
        tableauTantiemesInitialise = {
            'Postes de provisions': [provision.Nom for provision in LstProvisions],
            'Description':[provision.Description for provision in LstProvisions],
            'Description longue':[provision.DescriptionLongue for provision in LstProvisions],  
            'ID prestation':[provision.IDPrestation for provision in LstProvisions],
            'ID tantiemes':[provision.IDTantiemes for provision in LstProvisions],
            'Tantiemes': [LaResidence.DfTantiemes.loc[(LaResidence.DfTantiemes["IDTantiemes"] == provision.IDTantiemes) & (LaResidence.DfTantiemes["Numéro de lot"].isin(self.LotsDontOnVeutCalculerLesCharges)), 'Tantièmes'].sum() for provision in LstProvisions],
            'Tantiemes totaux': [LaResidence.DfTantiemes.loc[LaResidence.DfTantiemes["IDTantiemes"] == provision.IDTantiemes, 'Tantièmes'].sum() for provision in LstProvisions],
            'Charge': float(0),
            'Provisions':[provision.Provision for provision in LstProvisions],
            'Charges pour les lots sélectionnés': float(0)
        }
        self.DfCharges= pd.DataFrame(tableauTantiemesInitialise).sort_values(by='Provisions', ascending=False)
        self.DfCharges['TopConsommationDeChauffage'] = self.DfCharges['ID prestation'].isin([chaudiere.IDPrestation for chaudiere in self.ChaudieresDeLaResidence])

    def Etape1ParametrerLesTemperatures(self, TemperatureLot=19, TemperatureExterieure=19, TemperatureResidence=19,
        NbHeuresDeChauffe=2000, TemperatureEauFroide=15, consommationEauChaudeM3=30, consommationEauChaudeM3Residence=1600,
        volumeBallonEauChaude=3,temperatureSeuilBallonEauChaude=52, temperatureEauChaude=60):
        """
        Méthode permettant de paramétrer les températures pour le calcul des charges de chauffage.
        La température de la résidence inclue celle des lots sélectionnées, la temperature des lots non sélectionnés n'est pas la température de la résidence 
        """
        #Paramètres de température et eau chaude sanitaire
        self.TemperatureLot = TemperatureLot
        self.TemperatureExterieure = TemperatureExterieure
        self.TemperatureResidence = TemperatureResidence
        self.TemperatureEauFroide=TemperatureEauFroide
        self.TemperatureEauChaude=temperatureEauChaude #<50°C = Legionelle >70°C = Brulures et entartrage
        self.TemperatureSeuilBallonEauChaude=temperatureSeuilBallonEauChaude
        self.ConsommationEauChaudeM3=consommationEauChaudeM3
        self.ConsommationEauChaudeM3Residence=consommationEauChaudeM3Residence
        self.VolumeBallonEauChaudeM3=volumeBallonEauChaude
        self.NombreHeuresDeChauffe=NbHeuresDeChauffe
        self.flagPasDeChauffageUtilise=max(TemperatureResidence,TemperatureLot)<=TemperatureExterieure

        #Calcul de la puissance nécéssaire pour chauffer la résidence 
        self.PuissanceDeChauffeNecessaireEnWatt=self.CaracteristiquesDeLaResidence.VolumeTotalAChaufferM3*self.CaracteristiquesDeLaResidence.CoefficientIsolation*max(0,(self.TemperatureResidence-self.TemperatureExterieure))
        self.PuissanceDeChauffeNecessaireEnkWh=self.NombreHeuresDeChauffe*self.PuissanceDeChauffeNecessaireEnWatt/1000

        #Calcul de la puissance nécéssaire pour chauffer l'eau chaude sanitaire
        self.PuissanceEauChaudeNecessaireEnkWh = self.ConsommationEauChaudeM3Residence * 1.163 * (self.TemperatureEauChaude-self.TemperatureEauFroide)

        #Calcul des charges pour chaque chaudière en fonction de l'ordre d'utilisation
        ###Initialisation de la puissance de chauffe restante à distribuer entre les chaudières
        self.PuissanceDeChauffageRestantekWh=self.PuissanceDeChauffeNecessaireEnkWh
        self.PuissanceDeChauffeEauRestantekWh=self.PuissanceEauChaudeNecessaireEnkWh

        #On calcule la puissance minimum pour chauffer l'ECS 
        for chaudiere in self.ChaudieresDeLaResidence:
            #Calcul de la puissance de chauffe eau annuelle en kWh utilisée pour cette chaudière
            puissanceEauChaudeMinimumChaudierekW=min(
                chaudiere.ProductionMaxkW,
                self.VolumeBallonEauChaudeM3*1.163*(self.TemperatureEauChaude-self.TemperatureSeuilBallonEauChaude)/(chaudiere.SeuilDureeActivationMn/60)
            )
            ConditionChaudiereUtiliseePourECS=puissanceEauChaudeMinimumChaudierekW>chaudiere.SeuilFonctionnementPct*chaudiere.ProductionMaxkW and self.PuissanceDeChauffeEauRestantekWh>0
            if ConditionChaudiereUtiliseePourECS: 
                #Cette chaudière peut être utilisée pour chauffer toute l'eau chaude
                heuresActivationReelles=self.PuissanceDeChauffeEauRestantekWh/puissanceEauChaudeMinimumChaudierekW

                chaudiere.PuissanceUtiliseeEauChaudekWh=min(
                    puissanceEauChaudeMinimumChaudierekW*8760,
                    self.PuissanceDeChauffeEauRestantekWh)

                #On stocke la puissance minimale nécéssaire comme creux et pic de prod potentiel en kW
                chaudiere.PicProductionkW=puissanceEauChaudeMinimumChaudierekW
                chaudiere.CreuxProductionkW=puissanceEauChaudeMinimumChaudierekW
                self.PuissanceDeChauffeEauRestantekWh-=chaudiere.PuissanceUtiliseeEauChaudekWh 
      
            ##On calcule la puissance minimum pour chauffer la résidence
            chaudiere.PuissanceUtiliseeChauffagekWh=min(
                (chaudiere.ProductionMaxkW-(puissanceEauChaudeMinimumChaudierekW*ConditionChaudiereUtiliseePourECS))*self.NombreHeuresDeChauffe,
                self.PuissanceDeChauffageRestantekWh)
           
            chaudiere.PicProductionkW+=(chaudiere.PuissanceUtiliseeChauffagekWh/self.NombreHeuresDeChauffe)
            chaudiere.CreuxProductionkW=puissanceEauChaudeMinimumChaudierekW*ConditionChaudiereUtiliseePourECS if puissanceEauChaudeMinimumChaudierekW*ConditionChaudiereUtiliseePourECS<chaudiere.CreuxProductionkW else chaudiere.CreuxProductionkW
            self.PuissanceDeChauffageRestantekWh-=chaudiere.PuissanceUtiliseeChauffagekWh
              
            #Calcul du coût de la charge pour cette chaudière
            coutDeLaCharge=(chaudiere.PuissanceUtiliseeChauffagekWh+chaudiere.PuissanceUtiliseeEauChaudekWh)*chaudiere.PrixkWh

            #Mise à jour dans le tableau des charges
            self.DfCharges.loc[self.DfCharges['ID prestation'] == chaudiere.IDPrestation, 'Charge'] =  (not self.flagPasDeChauffageUtilise) * coutDeLaCharge

    def Etape2ConstruireTableauDeCharges (self,IDPrestation, LstPrestationsSelectionnees: list[Prestation]):
        """
        Méthode permettant de calculer les charges totales de copropriété en fonction des prestations et des provisions.
        """
        #Sauvegarder la liste de prestations sélectionnées
        self.PrestationsSelectionnees = LstPrestationsSelectionnees 
        #Réinitialiser les charges à 0
        self.DfCharges.loc[self.DfCharges['ID prestation'] == IDPrestation, 'Charge'] = float(0)

        #Calculer les charges totales 
        CoutReelDuPosteDeProvision = 0
        #Pour chaque provision on checke si on a des prestations associées
        for prestation in self.PrestationsSelectionnees:
            #On ajoute le coût de la prestation aux charges totales
            CoutReelDuPosteDeProvision += prestation.Cout
        #Si aucune prestation n'est associée à la provision, on prend le coût de la provision
        #On ajoute le coût réel du poste de provision aux charges totales
        self.DfCharges.loc[self.DfCharges['ID prestation'] == IDPrestation, 'Charge'] = CoutReelDuPosteDeProvision if CoutReelDuPosteDeProvision > 0 else self.DfCharges.loc[self.DfCharges['ID prestation'] == IDPrestation, 'Provisions'].iloc[0]

    def Etape3CalculerLesChargesParLot (self,IDPrestation,ConsommationEnEauM3=0):
        """
        Méthode permettant de calculer les charges par lot en fonction des tantièmes et des charges totales.
        """
        if IDPrestation=="EAU":
            #Calcul de la charge résultant de la consommation d'eau saisie pour ce poste de provision
            self.DfCharges.loc[self.DfCharges['ID prestation'] == IDPrestation, 'Charge'] =self.DfCharges.Provisions
            self.DfCharges.loc[self.DfCharges['ID prestation'] == IDPrestation, 'Charges pour les lots sélectionnés'] = CalculateurDeCharges.CalculerLeCoutDeEauCourante(ConsommationEnEauM3)

        else:
        #Pour chaque tantièmes on calcul les couts
            self.DfCharges.loc[self.DfCharges['ID prestation'] == IDPrestation, 'Charges pour les lots sélectionnés'] = (
                (self.DfCharges.Charge * self.DfCharges.Tantiemes) / self.DfCharges['Tantiemes totaux'])*(
                    0.3 + 0.7 * (self.TemperatureLot - self.TemperatureExterieure) / max(0.001, (self.TemperatureResidence - self.TemperatureExterieure)) if self.DfCharges.TopConsommationDeChauffage.any() else 1)
    
    def CalculerLeCoutDeEauCourante(consommationEauEnM3):
        """
        Méthode permettant de calculer le coût de l'eau courante en fonction de la consommation en m3 pour Noisy le Sec (Est Ensemble)
        """
        TaxeEtRedevances=3.3254
        TVA=1.08
        if consommationEauEnM3 <= 10:
            return consommationEauEnM3 * TaxeEtRedevances*TVA
        elif consommationEauEnM3 <= 28:
            return 10*TaxeEtRedevances*TVA+(1.1988+TaxeEtRedevances) * (consommationEauEnM3 - 10)*TVA
        elif consommationEauEnM3 <= 86:
            return 10*TaxeEtRedevances*TVA+(1.1988+TaxeEtRedevances) * 18*TVA+(1.3320+TaxeEtRedevances) * (consommationEauEnM3 - 28)*TVA
        elif consommationEauEnM3 <= 101:
            return 10*TaxeEtRedevances*TVA+(1.1988+TaxeEtRedevances) * 18*TVA+(1.3320+TaxeEtRedevances) *58*TVA+(1.3720+TaxeEtRedevances) * (consommationEauEnM3 - 86)*TVA
        elif consommationEauEnM3 <= 131:
            return 10*TaxeEtRedevances*TVA+(1.1988+TaxeEtRedevances) * 18*TVA+(1.3320+TaxeEtRedevances) *58*TVA+(1.3720+TaxeEtRedevances) * 15 *TVA+(1.42+TaxeEtRedevances) * (consommationEauEnM3 - 101)*TVA
        elif consommationEauEnM3 <= 140:
            return 10*TaxeEtRedevances*TVA+(1.1988+TaxeEtRedevances) * 18*TVA+(1.3320+TaxeEtRedevances) *58*TVA+(1.3720+TaxeEtRedevances) * 15 *TVA+(1.42+TaxeEtRedevances) * 30*TVA+(1.4919+TaxeEtRedevances) * (consommationEauEnM3 - 131)*TVA
        else:
            return 10*TaxeEtRedevances*TVA+(1.1988+TaxeEtRedevances) * 18*TVA+(1.3320+TaxeEtRedevances) *58*TVA+(1.3720+TaxeEtRedevances) * 15 *TVA+(1.42+TaxeEtRedevances) * 30*TVA+(1.4919+TaxeEtRedevances) * 9*TVA+(1.5366+TaxeEtRedevances) * (consommationEauEnM3 - 140)*TVA

#Import de données de provision, prestations et tantièmes
@st.cache_data 
def ImporterDonneesDeLaResidence(): 
    DonneesDeLaResidence= pd.read_excel("input.xlsx", sheet_name=["Provisions", "Prestations", "Lots","Residence","Chauffage central"])
    #Récupérer un dictionnaire de tantièmes pour les lots 
    DfLots =pd.melt( 
        DonneesDeLaResidence["Lots"],
        id_vars=[
            "Numéro de lot",
            "Description",
        ],  # <--- Vos 2 colonnes fixes à conserver
        var_name="IDTantiemes",  # Nom pour la colonne qui contiendra les anciens noms de colonnes
        value_name="Tantièmes",  # Nom pour la colonne qui contiendra les valeurs
    )  
    

    residence = Residence(
        DonneesDeLaResidence["Residence"].iloc[0]["Label"],
        DonneesDeLaResidence["Residence"].iloc[0]["Volume à chauffer en m3"],
        DonneesDeLaResidence["Residence"].iloc[0]["Coefficient d'isolation"],
        DfLots
        )

    LstChaudieres = [Chaudiere(
        row["Type de chaudière"], 
        row["ID poste de provision"],

        row["Unité"],
        row["Prix de l'unité"],
        row["kWh par unité"],

        row["Production maximum en kW"],
        row["Description"],
        row["Seuil de fonctionnement (%)"],
        row["Seuil de durée d'activation (mn)"]
        
        ) for index, row in DonneesDeLaResidence["Chauffage central"].iterrows()]      

    LstProvisions = [Provision(
        row["Label de la provision"], 
        row["Provision"],
        row["Description"],
        row["ID"],
        row["ID tantiemes"],
        row["Description longue"]
        ) for index, row in DonneesDeLaResidence["Provisions"].iterrows()]

    LstPrestations = [Prestation(
        row["Label de la prestation"], 
        row["Total TTC"],
        row["Description"],
        row["Prestataire"],
        row["ID prestation"],
        (row["Prestation choisie actuellement"]=="X")
    ) for index, row in DonneesDeLaResidence["Prestations"].iterrows()]
    return DfLots, LstProvisions, LstPrestations,residence, LstChaudieres

DfLots, LstProvisions, LstPrestations,LaResidence, LstChaudieres = ImporterDonneesDeLaResidence()
##################################
# Début de l'affiche du site web 
##################################

#Navigation à gauche
with st.sidebar:
    st.title("Navigation")
    st.markdown("[🏬 Section 1 : Sélection des lots](#section-1)")
    st.markdown("[📋 Section 2 : Sélection des prestations](#section-2)")
    st.markdown("[💰 Section 3 : Visualisation des charges](#section-3)")
    st.sidebar.write(f"RAM utilisée: {psutil.virtual_memory().percent} %")
    st.sidebar.write(f"CPU: {psutil.cpu_percent()} %")

# Titre de l'application
st.title("Calculateur de charges de copropriété")

with st.form("formulaireSaisieParametres"):
    # SECTION 1 : Sélection des lots
    st.subheader("1. Sélection des lots",anchor="section-1")

    st.write("Ce calculateur permet d'estimer les charges de copropriété en fonction des prestations sélectionnées et des tantièmes des lots choisis. Sélectionnez les lots et les prestations pour voir le calcul des charges:")

    # Un widget interactif : une boîte de saisie de texte
    LstLotsChoisis = st.multiselect(
        "Lots de la résidence à inclure dans le calcul des charges",
        options=DfLots["Numéro de lot"].tolist(),
        format_func=lambda numeroDelot: DfLots[DfLots['Numéro de lot'] == numeroDelot]['Description'].iloc[0]) 

    #Initialisation du calculateur de charges avec les lots choisis et les provisions
    SimulationEnCours=CalculateurDeCharges(LstLotsChoisis, LstProvisions,LaResidence,LstChaudieres)

    #SECTION 2 : Paramétrage des prestations et des charges 
    st.subheader("2. Paramétrage des prestations et des charges",anchor="section-2")
    #Choix de simuler la consommation de chauffage à partir de la température
    colGauche, colDroite= st.columns(2)

    with colDroite:
        consommationEauEnM3=st.number_input("Saisissez la consommation d'eau individuelle d'eau totale (M3):",0,100000,100,key=f"consommationEauIndividuelles")
        consommationEauChaudeM3=st.number_input("Saisissez la consommation individuelle d'eau chaude inclus (M3):",0,consommationEauEnM3,30,key=f"consommationEauChaudeIndividuelle")
        consommationEauChaudeM3Residence=st.number_input("Saisissez la consommation d'eau chaude annuelle de toute la résidence (M3):",consommationEauChaudeM3,1000000,1600,key=f"consommationEauChaudeResidence")
        volumeBallonEauChaudeM3=st.number_input("Saisissez le volume du ballon de l'eau chaude sanitaire (M3)",0,10,3,key=f"num_volumeBallon")
        nbHeuresDeChauffe=st.number_input("Saisissez le nombre d'heures d'activité du chauffage central durant un hiver (heures):",0,8760,2000,key=f"num_nbHeuresDeChauffe")
    with colGauche:
        temperatureExterieure = st.slider("Température à l'extérieur de la résidence en hiver (°C)", -30, 25, 5, key=f"temp_ext")
        temperatureResidence = st.slider("Température moyenne maintenue dans la résidence en hiver (°C)", 0, 25, 19, key=f"temp_res")
        temperatureDuLot = st.slider("Température intérieure des lots en hiver (°C)", 0, 25, 19, key=f"temp_lot")
        temperatureEauFroide = st.slider("Température de l'eau froide à chauffer (°C)", -10, 50, 14, key=f"temp_eau_froide") 
        temperatureSeuilBallonEauChaude=st.slider("Seuil de température du ballon d'eau (°C)", 50, 70, 52, key=f"temp_seuil_eauChaude") 
        temperatureEauChaude=st.slider("Température de l'eau chaude sanitaire moyenne (°C)", 40, 70, 60, key=f"temp_eau_chaude")
    submit = st.form_submit_button("Calculer les charges", type="primary",  # bouton coloré (bleu par défaut)
        use_container_width=True ) # prend toute la largeur
#Intégration des parametres
SimulationEnCours.Etape1ParametrerLesTemperatures(
    temperatureDuLot,temperatureExterieure,temperatureResidence, 
    nbHeuresDeChauffe,  temperatureEauFroide, consommationEauChaudeM3,
    consommationEauChaudeM3Residence,volumeBallonEauChaudeM3,temperatureSeuilBallonEauChaude,temperatureEauChaude)

# Une condition pour afficher un message si le texte est rempli 
if LstLotsChoisis:
    st.write("**Vous avez sélectionné les lots suivants :**")
    for numeroDeLot in LstLotsChoisis:
        # Chaque st.write crée automatiquement une nouvelle ligne
        st.write(f"🔹 {numeroDeLot} - {DfLots[DfLots['Numéro de lot'] == numeroDeLot]['Description'].iloc[0]}")

with st.expander("Paramètres de température et de chauffage",icon="♨️"):
    with st.container(border=True):
        st.write(f"Puissance de chauffe nécessaire pour le chauffage central : {SimulationEnCours.PuissanceDeChauffeNecessaireEnkWh:.0f} kWh")
        st.write(f"Puissance de chauffe nécéssaire pour l'eau chaude sanitaire (ECS): {SimulationEnCours.PuissanceEauChaudeNecessaireEnkWh:.0f} kWh")
        st.write(f"Paramètres des chaudières :")
        for chaudiere in SimulationEnCours.ChaudieresDeLaResidence:
            st.write(f"**Chaudière : {chaudiere.Nom}**")
            st.write(f"- Production max. {chaudiere.ProductionMaxkW} kW, Prix du combustible: {chaudiere.PrixUniteCombustible:.2f}€/{chaudiere.NomUniteCombustible}, consommation: {(chaudiere.PuissanceUtiliseeChauffagekWh+chaudiere.PuissanceUtiliseeEauChaudekWh)/chaudiere.kWhUniteCombustible:.2f} {chaudiere.NomUniteCombustible}, Prix standardisé: {chaudiere.PrixkWh:.4f} €/kWh")
            st.write(f"- Puissance utilisé au pic : {chaudiere.PicProductionkW:.2f} kW / Taux d'utilisation au pic: {(chaudiere.PicProductionkW/chaudiere.ProductionMaxkW)*100:.0f}%")
            st.write(f"- Puissance utilisée au creux : {chaudiere.CreuxProductionkW:.0f} kW / Taux d'utilisation au creux: {(chaudiere.CreuxProductionkW/chaudiere.ProductionMaxkW)*100:.0f}%")
            st.write(f"- Coût de la charge lié au chauffage central : {chaudiere.PuissanceUtiliseeChauffagekWh*chaudiere.PrixkWh:.2f} €")
            st.write(f"- Coût de la charge lié à l'eau chaude sanitaire : {chaudiere.PuissanceUtiliseeEauChaudekWh*chaudiere.PrixkWh:.2f} €")
            st.write(f"- Description : {chaudiere.Description}")
        if SimulationEnCours.PuissanceDeChauffageRestantekWh>0:
            st.write("Attention, il n'y a pas assez de puissance pour chauffer la résidence !")
        if SimulationEnCours.PuissanceDeChauffeEauRestantekWh>0:
            st.write("Attention, il n'y a pas assez de puissance pour chauffer l'eau chaude sanitaire !")
if SimulationEnCours.PuissanceDeChauffeEauRestantekWh>0:
    st.warning("Attention, il n'y a pas assez de puissance de chauffe pour chauffer les logements en hiver !", icon="⚠️")
if SimulationEnCours.PuissanceDeChauffeEauRestantekWh>0:
    st.warning("Attention, il n'y a pas assez de puissance de chauffe pour chauffer l'eau chaude sanitaire !", icon="⚠️")
if SimulationEnCours.PuissanceDeChauffeEauRestantekWh==0 and SimulationEnCours.PuissanceDeChauffageRestantekWh==0:
    st.success("La puissance de chauffage est suffisante pour l'eau chaude et le chauffage l'hiver", icon="✅")

#Initialisation des prestations choisies
prestationsChoisies = []

#Afficher les provisions et donner l'option de sélectionner une prestation s'il y a en a une
if SimulationEnCours.DfCharges[SimulationEnCours.DfCharges['Tantiemes'] > 0].empty:
    st.write("Pas de lots sélectionnés.")
else:
    st.write("Pour chaque poste de provision, vous pouvez sélectionner une ou plusieurs prestations:")

TopIndicateurProvInfA500,TopIndicateurProvInfA1500,TopIndicateurProvSupA1500=False,False,False
for index, row in SimulationEnCours.DfCharges[SimulationEnCours.DfCharges['Tantiemes'] > 0].iterrows():
    #Initialisation
    IDPrestationActuel=row["ID prestation"]
    MontantProvision=row["Provisions"]
    TopConsommationDeChauffage=row["TopConsommationDeChauffage"]

    #Affichage des règles selon le montant de la provision
    if MontantProvision>1500 and not TopIndicateurProvSupA1500:
        TopIndicateurProvSupA1500=True
        st.write("**Les provisions suivantes sont supérieures à 1500€HT par an, le syndic est dans l'obligation de mettre en concurrence les fournisseurs et de consulter le conseil syndical.**")
    if MontantProvision<=1500 and not TopIndicateurProvInfA1500:
        TopIndicateurProvInfA1500=True
        st.write("**Les provisions suivantes sont inférieures à 1500€HT par an, le syndic n'est plus dans l'obligation de mettre en concurrence les fournisseurs.**")
    if MontantProvision<=500 and not TopIndicateurProvInfA500:
        TopIndicateurProvInfA500=True
        st.write("**Les provisions suivantes sont inférieures à 500€HT par an, le syndic n'a plus l'obligation de consulter le conseil syndical.**")
    
    #Début du bloc d'explication pour chaque provision
    with st.expander(f"**{row['Postes de provisions']} - Provision: {MontantProvision:.0f}€/an**"):

        ConditionProvisionCommune=not(TopConsommationDeChauffage) and not(IDPrestationActuel =="EAU")

        #Cas où on sélectionne des prestations dans la liste 
        if ConditionProvisionCommune:
            #Valeur définie selon les prestations choisies  
            optionsDePrestations = [prestation for prestation in LstPrestations if prestation.IDPrestation == IDPrestationActuel]
            prestationsEnCours = [prestation for prestation in optionsDePrestations if prestation.TopPrestationChoisie]
            if optionsDePrestations:
                prestationsSelectionnees = st.multiselect(
                    f"Choisissez un ou plusieurs devis pour ce poste",
                    options=optionsDePrestations,
                    format_func=lambda prestation: f"🔹 {prestation.Nom} - {prestation.Prestataire} - {prestation.Cout:.2f} €/an",
                    key=f"prestations_{IDPrestationActuel}",
                    default=prestationsEnCours
                )
                #Ajout des prestations à la liste des prestations choisies pour le calcul des charges
                prestationsChoisies.extend(prestationsSelectionnees)
            else: #Cas où il n'y a pas de prestations associées à la provision, on ne fait rien
                prestationsSelectionnees=[]       
                st.write("Aucune prestation n'est associée à ce poste de provision, le calcul des charges se fera sur la base de la provision.") 
            #Calcul de la charge résultant des prestations choisies pour ce poste de provision
            SimulationEnCours.Etape2ConstruireTableauDeCharges(IDPrestationActuel, prestationsSelectionnees)
        else:#On met à 0 sinon ça ressort les prestations choisie des postes de provisions précédentes 
            prestationsSelectionnees=[]

        #Intégrer les charges par lots sélectionnés dans le tableau des charges 
        SimulationEnCours.Etape3CalculerLesChargesParLot(IDPrestationActuel, ConsommationEnEauM3=consommationEauEnM3)
        
        #Récupérer le cout pour les lots
        coutResidence = SimulationEnCours.DfCharges.loc[SimulationEnCours.DfCharges['ID prestation'] == IDPrestationActuel, 'Charge'].iloc[0]
        coutLots=SimulationEnCours.DfCharges.loc[SimulationEnCours.DfCharges['ID prestation'] == IDPrestationActuel, 'Charges pour les lots sélectionnés'].iloc[0]
        
        #Boucles d'explication des charges
        colPrestation, colSynthese = st.columns(2)
        with colPrestation:
            st.write(f"{row['Description']}")
            st.write(f"{row['Description longue']}")
            for prestation in prestationsSelectionnees:
                with st.container(border=True):
                    st.write(f"**{prestation.Nom} - {prestation.Cout:.2f} €/an**")
                    st.write(f"Prestataire: **_{prestation.Prestataire}_**")
                    st.write(f"Description: {prestation.Description}")
        with colSynthese:
            with st.container(border=True):
                st.write(f"Coût de la provision : {MontantProvision:.2f} €")
                st.write(f"Coût de la charge pour la résidence : {coutResidence:.2f} €")
                st.write(f"**Détail du calcul**")
                st.write(f"Les lots sélectionnés corresponent au total à {row['Tantiemes']:.0f} tantièmes associés aux lots, pour {row['Tantiemes totaux']:.0f} tantièmes totaux de la résidence.")
                
                #Explication du calcul des charges pour les lots sélectionnés
                if ConditionProvisionCommune:
                    st.latex(f"{coutResidence:.0f}\\times \\frac{{{row['Tantiemes']:.0f}}}{{{row['Tantiemes totaux']:.0f}}} = {coutLots:.2f}\\text{{ €/an}}")
                elif SimulationEnCours.flagPasDeChauffageUtilise:
                    st.write(f"La température extérieure est supérieure à la température dans les lots sélectionnées et dans la résidence, donc il n'y a pas de consommation de chauffage.")
                elif TopConsommationDeChauffage:
                    st.latex(f"{coutResidence:.0f} \\times \\frac{{{row['Tantiemes']:.0f}}}{{{row['Tantiemes totaux']:.0f}}} \\times \\left( 30\\% + 70\\% \\times \\frac{{{SimulationEnCours.TemperatureLot}\\text{{°C}} - {SimulationEnCours.TemperatureExterieure}\\text{{°C}}}}{{{SimulationEnCours.TemperatureResidence}\\text{{°C}} - {SimulationEnCours.TemperatureExterieure}\\text{{°C}}}} \\right) = {coutLots:.2f}\\text{{ €/an}}")
                else:
                    st.write(f"La consommation d'eau courante est de {consommationEauEnM3} m3.")
                st.write(f"Le coût de la charge pour les lots sélectionnés est donc de {coutLots:.2f} € par an ou {coutLots/12:.2f} € par mois.")

#SECTION 3 : Résultat du calcul des charges
st.subheader("3. Résultat du calcul des charges",anchor="section-3")
#Afficher tableau des charges                    
st.dataframe(SimulationEnCours.DfCharges.drop(columns=['ID prestation','Description longue',"TopConsommationDeChauffage", 'ID tantiemes','Description']))

#Afficher les charges annuelles et mensuelles totales pour les lots sélectionnés
st.success(f"**Total des charges annuelles pour les lots sélectionnés : {SimulationEnCours.DfCharges['Charges pour les lots sélectionnés'].sum():.2f} €**")
st.success(f"**Total des charges mensuelles pour les lots sélectionnés : {SimulationEnCours.DfCharges['Charges pour les lots sélectionnés'].sum()/12:.2f} €**")

# Création des camemberts avec Plotly
CamembertChargesLots = px.pie(
    SimulationEnCours.DfCharges.drop(columns=['ID prestation', 'ID tantiemes','Description']), 
    values="Charges pour les lots sélectionnés", 
    names="Postes de provisions", 
    title="Répartition des charges annuelles des lots choisis par catégorie",
    hole=0.3  # Optionnel : ajoute un trou au centre (style Donut)
)

CamembertChargesLots.update_traces(
    textposition="inside",          # Force le texte à rester dans les tranches
    textinfo="percent+label",       # Ce qu'on affiche
    insidetextorientation="radial"  # Oriente le texte pour gagner de la place
)

CamembertChargesLots.update_layout(
    height=900,
    legend=dict(
        orientation="h",
        yanchor="top",
        y=-0.2,
        xanchor="center",
        x=0.5,
        font=dict(size=10),      # Réduit la taille de la police
        entrywidth=250,          # Augmente la largeur de chaque colonne (en pixels)
        entrywidthmode="pixels"
    ),
    margin=dict(b=150)
)
# Affichage dans Streamlit
st.plotly_chart(CamembertChargesLots, use_container_width=True)