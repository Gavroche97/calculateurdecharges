import streamlit as st
import pandas as pd

TANTIEMES_TOTAUX=10007
VOLUME_A_CHAUFFER=10142 #M3 à chauffer dans la résidence, estimation par tantieme
COEFF_ISOLATION=0.5 #0.4 à 0.8 : Très bien isolé (RT2012 / BBC) - 0.9 à 1.1 : Isolation standard (Années 90/2000) - 1.2 à 1.6 : Mal isolé (Passoire thermique).

# Commande pour 
st.set_page_config(
    page_title="Calculateur de Charges",
    layout="wide"  # Force l'affichage sur toute la largeur de l'écran
)
###################################################
# Classe de Calculateur de charges de copropriété #
###################################################

class Lot:
    """
    Classe d'objet permettant de définir un lot de copropriété avec ses ID et ses tantièles associés aux subdivisions.
    """
    def __init__(self,description, IDNotaire, DicoTaxonomieTantiemes: dict):
        self.IDNotaire = IDNotaire
        self.Description = description
        #Créer un dico pour initialiser le tableau des tantièmes
        tableauTantiemesInitialise = {
            'Label des subdivisions': DicoTaxonomieTantiemes.keys(),
            'Tantiemes':DicoTaxonomieTantiemes.values()
        } 
        self.DfTantiemes= pd.DataFrame(tableauTantiemesInitialise) 

class Prestation:
    """
    Classe d'objet permettant de définir une prestation de copropriété avec son nom et son coût associé.
    """
    def __init__(self, Nom, Cout,Description,Prestataire,IDPrestation=None):
        self.Nom = Nom
        self.Cout = Cout
        self.Description = Description
        self.IDPrestation = IDPrestation
        self.Prestataire=Prestataire

class Provision:
    """
    Classe d'objet permettant de définir une provision de copropriété avec son nom et son montant associé.
    """ 
    def __init__(self, Nom, Provision,Description,IDPrestation,IDTantiemes, TopConsommationDeChauffage):
        self.Nom = Nom 
        self.Provision = Provision 
        self.Description = Description
        self.IDPrestation = IDPrestation
        self.IDTantiemes = IDTantiemes
        self.TopConsommationDeChauffage = TopConsommationDeChauffage

class CalculateurDeCharges:
    """
    Classe d'objet permettant de calculer les charges de copropriété en fonction des lots, des prestations et des provisions.
    """
    def __init__(self,LstLot:  list[Lot],
                LstProvisions: list[Provision], 
                TantiemesTotaux=10000):

        #Initialiser les attributs de la classe
        self.Lots = LstLot 
        self.TantiemesTotaux = TantiemesTotaux

        #Créer un dico pour initialiser le tableau des tantièmes
        tableauTantiemesInitialise = {
            'Postes de provisions': [provision.Nom for provision in LstProvisions],
            'Description':[provision.Description for provision in LstProvisions],
            'ID prestation':[provision.IDPrestation for provision in LstProvisions],
            'ID tantiemes':[provision.IDTantiemes for provision in LstProvisions],
            'TopConsommationDeChauffage': [provision.TopConsommationDeChauffage for provision in LstProvisions],
            'Tantiemes': 0,
            'Charge': float(0),
            'Provisions':[provision.Provision for provision in LstProvisions],
        }
        self.DfCharges= pd.DataFrame(tableauTantiemesInitialise).sort_values(by='Provisions', ascending=False)

        #Incrémenter les tantièmes dans le tableau des charges
        for lot in LstLot:
            self.DfCharges['Tantiemes'] += self.DfCharges['ID tantiemes'].map(
                lot.DfTantiemes.set_index('Label des subdivisions')['Tantiemes']).fillna(0)

    def Etape1ConstruireTableauDeCharges (self, LstPrestationsSelectionnees: list[Prestation]):
        """
        Méthode permettant de calculer les charges totales de copropriété en fonction des prestations et des provisions.
        """
        #Sauvegarder la liste de prestations sélectionnées
        self.PrestationsSelectionnees = LstPrestationsSelectionnees
        #Réinitialiser les charges à 0
        self.DfCharges['Charge'] = float(0)

        #Itération pour calculer les charges totales
        for index, row in self.DfCharges.iterrows():
            CoutReelDuPosteDeProvision = 0
            #Pour chaque provision on checke si on a des prestations associées
            for prestation in self.PrestationsSelectionnees:
                #S'il y a des prestations associées à la provision, on ajoute le coût de la prestation aux charges totales
                if prestation.IDPrestation == row['ID prestation']:
                    CoutReelDuPosteDeProvision += prestation.Cout
            #Si aucune prestation n'est associée à la provision, on prend le coût de la provision
            if CoutReelDuPosteDeProvision==0:
                CoutReelDuPosteDeProvision=row['Provisions']
            #On ajoute le coût réel du poste de provision aux charges totales
            self.DfCharges.loc[self.DfCharges['ID prestation'] == row['ID prestation'], 'Charge'] = CoutReelDuPosteDeProvision

    def Etape2CalculerLesChargesParLot (self):
        """
        Méthode permettant de calculer les charges par lot en fonction des tantièmes et des charges totales.
        """
        #Pour chaque tantièmes on calcul les couts
        self.DfCharges['Charges pour les lots sélectionnés'] = self.DfCharges.Charge * self.DfCharges.Tantiemes / self.TantiemesTotaux

    def Etape3aParametrerLesTemperatures(self, TemperatureLot=19, TemperatureExterieure=19, TemperatureResidence=19, VolumeEnM3DeLaResidence=10000,CoefficientIsolation=1,NbHeuresDeChauffe=2000):
        """
        Méthode permettant de paramétrer les températures pour le calcul des charges de chauffage.
        La température de la résidence inclue celle des lots sélectionnées, la temperature des lots non sélectionnés n'est pas la température de la résidence 
        """
        #Paramètres de température
        self.TemperatureLot = TemperatureLot
        self.TemperatureExterieure = TemperatureExterieure
        self.TemperatureResidence = TemperatureResidence

        #Paramètres de résidence$
        self.VolumeAChaufferEnM3=VolumeEnM3DeLaResidence
        self.CoefficientIsolation=CoefficientIsolation
        self.NombreHeuresDeChauffe=NbHeuresDeChauffe

        self.flagPasDeChauffageUtilise=True if max(TemperatureResidence, TemperatureExterieure,TemperatureLot)==TemperatureExterieure else False

        #Calcul de la déperdition de chaleur
        self.PuissanceDeChauffeNecessaireEnWatt=self.VolumeAChaufferEnM3*self.CoefficientIsolation*max(0,(self.TemperatureResidence-self.TemperatureExterieure))
        self.PuissanceDeChauffeNecessaireEnKWH=self.NombreHeuresDeChauffe*self.PuissanceDeChauffeNecessaireEnWatt/1000

    def Etape3bCalculerLaConsommationIndividuelleDeChauffage (self, IDPrestation,
                Prixunitaire=500,#Biomasse: 392 pour CRAM, 392 pour PROCHALOR 
                ConsommationUnitaire=40):
        """
        Méthode permettant d'inclure la consommation individuelle de chauffage dans le calcul des charges par lot.
        """
        #Calcul de la charge totale pour la résidence
        ChargeTotaleDeLaResidence=ConsommationUnitaire * Prixunitaire

        #Calcul de la charge pour le copropriétaire
        ChargeCommuneDeGranule=ChargeTotaleDeLaResidence * 0.3

        ecartTemperatureResidenceEtExterieur=self.TemperatureResidence - self.TemperatureExterieure

        ChargeIndividuelle=ChargeTotaleDeLaResidence *0.7 * ((self.TemperatureLot - self.TemperatureExterieure) / ecartTemperatureResidenceEtExterieur if ecartTemperatureResidenceEtExterieur!=0 else 1)

        ChargeTotalePourLeLot=ChargeCommuneDeGranule + ChargeIndividuelle

        #Mise à jour dans le tableau des charges
        self.DfCharges.loc[self.DfCharges['ID prestation'] == IDPrestation, 'Charge'] = 0 if self.flagPasDeChauffageUtilise else ChargeTotalePourLeLot
        self.Etape2CalculerLesChargesParLot()

#Import de données de provision, prestations et tantièmes
@st.cache_data
def ImporterDonneesDeLaResidence():
    DonneesDeLaResidence= pd.read_excel("input.xlsx", sheet_name=["Provisions", "Prestations", "Lots"])
    #Récupérer un dictionnaire de tantièmes pour les lots

    LstLots = [Lot(
        row["Description"], 
        row["Numéro de lot"],
        row.drop(["Numéro de lot", "Description"]).to_dict()
        ) for index, row in DonneesDeLaResidence["Lots"].iterrows()]    

    LstProvisions = [Provision(
        row["Label de la provision"], 
        row["Provision"],
        row["Description"],
        row["ID"],
        row["ID tantiemes"],
        row["Top consommation chauffage"]
        ) for index, row in DonneesDeLaResidence["Provisions"].iterrows()]

    LstPrestations = [Prestation(
        row["Label de la prestation"], 
        row["Total TTC"],
        row["Description"],
        row["Prestataire"],
        row["ID prestation"]
    ) for index, row in DonneesDeLaResidence["Prestations"].iterrows()]

    return LstLots, LstProvisions, LstPrestations

LstLots, LstProvisions, LstPrestations = ImporterDonneesDeLaResidence()
##################################
# Début de l'affiche du site web 
##################################

# Titre de l'application
st.title("Calculateur de charges de copropriété")

# Un sous-titre
st.subheader("Ce calculateur permet d'estimer les charges de copropriété en fonction des prestations sélectionnées et des tantièmes des lots choisis")
st.write("Sélectionnez les lots et les prestations pour voir le calcul des charges.")
# Un widget interactif : une boîte de saisie de texte
LstLotsChoisis = st.multiselect(
    "Choisissez un ou plusieurs lots :",
    options=LstLots,
    format_func=lambda lot: f"🔹 {lot.IDNotaire} - {lot.Description}") 

# Une condition pour afficher un message si le texte est rempli
if LstLotsChoisis:
    st.write("**Vous avez sélectionné les lots suivants :**")
    for lot in LstLotsChoisis:
        # Chaque st.write crée automatiquement une nouvelle ligne
        st.write(f"🔹 {lot.IDNotaire} - {lot.Description}")

#Initialisation du calculateur de charges avec les lots choisis et les provisions
SimulationEnCours=CalculateurDeCharges(LstLotsChoisis, LstProvisions,TANTIEMES_TOTAUX)
#Choix de simuler la consommation de chauffage à partir de la température
TopTemperature=st.toggle("Paramétrer un scénario de température précis", key=f"toggle_temperature")
if TopTemperature:
    col_temp1, col_temp2, col_temp3, col_nbHeures = st.columns(4)
    with col_temp1:
        temperatureExterieure = st.slider("Température à l'extérieur de la résidence (°C)", -10, 25, 20, key=f"temp_ext")
    with col_temp2:
        temperatureDuLot = st.slider("Température intérieure des lots (°C)", 0, 25, 25, key=f"temp_lot")
    with col_temp3:
        temperatureResidence = st.slider("Température moyenne de la résidence (°C)", 0, 25, 25, key=f"temp_res")
    with col_nbHeures:
        nbHeuresDeChauffe=st.number_input("Saisissez le nombre d'heures de chauffe",0,10000,2000)
    SimulationEnCours.Etape3aParametrerLesTemperatures(
        TemperatureLot=temperatureDuLot,TemperatureExterieure=temperatureExterieure,TemperatureResidence=temperatureResidence,
        VolumeEnM3DeLaResidence= VOLUME_A_CHAUFFER,CoefficientIsolation=COEFF_ISOLATION,NbHeuresDeChauffe= nbHeuresDeChauffe)

#Initialisation des prestations choisies
prestationsChoisies = []

#Afficher les provisions et donner l'option de sélectionner une prestation s'il y a en a une
for index, row in SimulationEnCours.DfCharges[SimulationEnCours.DfCharges['Tantiemes'] > 0].iterrows():
    #Est ce que c'est de la consommation de chauffage
    TopConsommationDeChauffage=pd.notna(row["TopConsommationDeChauffage"])

    with st.container(border=True):
        #Indiquer le poste de provision en gros puis la description en dessous
        st.markdown(f"<h3 style='text-align: center;'> {row['Postes de provisions']} </h3>",unsafe_allow_html=True)
        st.write(f"{row['Description']}")
        
        #Cas pour la consommation de chauffage
        #Si simulation selon températures activées
        if TopTemperature & TopConsommationDeChauffage:
            col1, col2 = st.columns(2)
            with col1:
                consommationUnitaire=st.number_input("Saisissez la consommation d'unité",0,1000,key=f"Conso_{row['ID prestation']}")
            with col2:
                coutUnitaire=st.number_input("Saisissez le coût unitaire",0,1000, key=f"Cout_{row['ID prestation']}")
            coutResidence=consommationUnitaire*coutUnitaire
            # Recalculer les charges par lot
            SimulationEnCours.Etape3bCalculerLaConsommationIndividuelleDeChauffage(row["ID prestation"],coutUnitaire,consommationUnitaire)
            prestationsSelectionnees = []
        else:
            #Valeur définie selon les prestations choisies  
            optionsDePrestations = [prestation for prestation in LstPrestations if prestation.IDPrestation == row['ID prestation']]
            if optionsDePrestations:
                prestationsSelectionnees = st.multiselect(
                        f"Choisissez un ou plusieurs devis pour ce poste",
                        options=optionsDePrestations,
                        format_func=lambda prestation: f"🔹 {prestation.Nom} - {prestation.Prestataire}",
                        key=f"prestations_{row['ID prestation']}"
                    )
            else:
                prestationsSelectionnees = []

            #Ajout des prestations à la liste des prestations choisies pour le calcul des charges
            prestationsChoisies.extend(prestationsSelectionnees)
            #Calcul de la charge résultant des prestations choisies pour ce poste de provision
            SimulationEnCours.Etape1ConstruireTableauDeCharges(prestationsChoisies)
        #Intégrer les charge dans le tableau des charges
        SimulationEnCours.Etape2CalculerLesChargesParLot()
        
        #Récupérer le cout pour les lots
        coutResidence = SimulationEnCours.DfCharges.loc[SimulationEnCours.DfCharges['ID prestation'] == row['ID prestation'], 'Charge'].iloc[0]
        coutLots=SimulationEnCours.DfCharges.loc[SimulationEnCours.DfCharges['ID prestation'] == row['ID prestation'], 'Charges pour les lots sélectionnés'].iloc[0]
        
        #Boucles d'explication des charges
        col1, col2 = st.columns(2)
        with col1:
            for prestation in prestationsSelectionnees:
                with st.container(border=True):
                    st.write(f"**{prestation.Nom}**")
                    st.write(f"Prestataire: **_{prestation.Prestataire}_**")
                    st.write(f"Description: {prestation.Description}")
        with col2:
            with st.container(border=True):
                st.write(f"Coût de la provision : {row['Provisions']:.2f} €")
                st.write(f"Coût de la charge pour la résidence : {coutResidence:.2f} €")
                st.write(f"**Détail du calcul**")
                st.write(f"Les lots sélectionnés corresponent au total à {row['Tantiemes']:.0f} tantièmes associés sur {SimulationEnCours.TantiemesTotaux} tantièmes totaux de la résidence.")
                if not(TopConsommationDeChauffage) or not(TopTemperature):
                    st.latex(f"{coutResidence:.0f}\\times \\frac{{{row['Tantiemes']:.0f}}}{{{SimulationEnCours.TantiemesTotaux}}} = {coutLots:.2f}\\text{{ €/an}}")
                elif SimulationEnCours.flagPasDeChauffageUtilise:
                    st.write(f"La température extérieure est supérieure à la température dans les lots sélectionnées et dans la résidence, donc il n'y a pas de consommation de chauffage.")
                else:
                    st.latex(f"{coutResidence:.0f} \\times \\frac{{{row['Tantiemes']:.0f}}}{{{SimulationEnCours.TantiemesTotaux}}} \\times \\left( 30\\% + 70\\% \\times \\frac{{{SimulationEnCours.TemperatureLot}\\text{{°C}} - {SimulationEnCours.TemperatureExterieure}\\text{{°C}}}}{{{SimulationEnCours.TemperatureResidence}\\text{{°C}} - {SimulationEnCours.TemperatureExterieure}\\text{{°C}}}} \\right) = {coutLots:.2f}\\text{{ €/an}}")
                st.write(f"Le coût de la charge pour les lots sélectionnés est donc de {coutLots:.2f} € par an ou {coutLots/12:.2f} € par mois.")

#Afficher tableau des charges                    
st.dataframe(SimulationEnCours.DfCharges.drop(columns=['ID prestation', 'ID tantiemes','Description','TopConsommationDeChauffage']))