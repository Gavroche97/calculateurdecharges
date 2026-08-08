import streamlit as st
import pandas as pd

#10007 tantiemes au total
#10142 M3 à chauffer dans la résidence, estimation par tantieme
#0.4 à 0.8 : Très bien isolé (RT2012 / BBC) - 0.9 à 1.1 : Isolation standard (Années 90/2000) - 1.2 à 1.6 : Mal isolé (Passoire thermique).
#On suppose que c'est le mododèle Herz Firematic 150 d'une capacité de 150kWh
#On suppose que c'est le modèle Atlantic Varmax 2 225 d'une capacité de 225kWh

# Commande pour 
st.set_page_config(
    page_title="Calculateur de Charges",
    layout="wide"  # Force l'affichage sur toute la largeur de l'écran
)
###################################################
# Classe de Calculateur de charges de copropriété #
###################################################
class Chaudiere:
    def __init__(self,Label, IDPrestation, PrixkWh, ProductionMaxkW,Ordre):
        self.Nom=Label
        self.IDPrestation=IDPrestation
        self.PrixkWh=PrixkWh 
        self.ProductionMaxkW=ProductionMaxkW
        self.PuissanceUtilisee=0
        self.OrdreUtilisation=Ordre

class Residence:
    def __init__(self,Label, TantiemesTotaux, VolumeTotalAChauffer, CoefficientIsolation):
        self.Nom=Label
        self.VolumeTotalAChaufferM3=VolumeTotalAChauffer
        self.TantiemesTotaux=TantiemesTotaux
        self.CoefficientIsolation=CoefficientIsolation
    
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
    def __init__(self, Nom, Provision,Description,IDPrestation,IDTantiemes):
        self.Nom = Nom 
        self.Provision = Provision 
        self.Description = Description
        self.IDPrestation = IDPrestation
        self.IDTantiemes = IDTantiemes

class CalculateurDeCharges:
    """
    Classe d'objet permettant de calculer les charges de copropriété en fonction des lots, des prestations et des provisions.
    """
    def __init__(self,LstLot:  list[Lot],
                LstProvisions: list[Provision], 
                LaResidence:Residence,
                LstChaudieres:list[Chaudiere]):

        #Initialiser les attributs de la classe
        self.Lots = LstLot 
        self.CaracteristiquesDeLaResidence=LaResidence
        self.ChaudieresDeLaResidence=sorted(LstChaudieres, key=lambda chaudiere: (chaudiere.OrdreUtilisation if chaudiere.OrdreUtilisation is not None else 999))

        self.TemperatureLot = 1
        self.TemperatureExterieure = 1
        self.TemperatureResidence=1

        #Créer un dico pour initialiser le tableau des tantièmes
        tableauTantiemesInitialise = {
            'Postes de provisions': [provision.Nom for provision in LstProvisions],
            'Description':[provision.Description for provision in LstProvisions],
            'ID prestation':[provision.IDPrestation for provision in LstProvisions],
            'ID tantiemes':[provision.IDTantiemes for provision in LstProvisions],
            'TopConsommationDeChauffage': [provision.IDPrestation in {chaudiere.IDPrestation for chaudiere in LstChaudieres} for provision in LstProvisions],
            'Tantiemes': 0,
            'Charge': float(0),
            'Provisions':[provision.Provision for provision in LstProvisions],
        }
        self.DfCharges= pd.DataFrame(tableauTantiemesInitialise).sort_values(by='Provisions', ascending=False)

        #Incrémenter les tantièmes dans le tableau des charges
        for lot in LstLot:
            self.DfCharges['Tantiemes'] += self.DfCharges['ID tantiemes'].map(
                lot.DfTantiemes.set_index('Label des subdivisions')['Tantiemes']).fillna(0)

    def Etape1aConstruireTableauDeCharges (self,IDPrestation, LstPrestationsSelectionnees: list[Prestation]):
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
        if CoutReelDuPosteDeProvision==0:
            CoutReelDuPosteDeProvision=row['Provisions']
        #On ajoute le coût réel du poste de provision aux charges totales
        self.DfCharges.loc[self.DfCharges['ID prestation'] == IDPrestation, 'Charge'] = CoutReelDuPosteDeProvision

    def Etape2CalculerLesChargesParLot (self,topScenarioDeTemperature=False):
        """
        Méthode permettant de calculer les charges par lot en fonction des tantièmes et des charges totales.
        """
        #Pour chaque tantièmes on calcul les couts
        if topScenarioDeTemperature:
            self.DfCharges.loc[self.DfCharges['TopConsommationDeChauffage']==True,'Charges pour les lots sélectionnés'] = (self.DfCharges.Charge.loc[self.DfCharges['TopConsommationDeChauffage']==True] * self.DfCharges.Tantiemes.loc[self.DfCharges['TopConsommationDeChauffage']==True]) / self.CaracteristiquesDeLaResidence.TantiemesTotaux * (0.3 + 0.7 * (self.TemperatureLot - self.TemperatureExterieure) / max(0.001, (self.TemperatureResidence - self.TemperatureExterieure)))
            self.DfCharges.loc[self.DfCharges['TopConsommationDeChauffage']==False,'Charges pour les lots sélectionnés'] = (self.DfCharges.Charge.loc[self.DfCharges['TopConsommationDeChauffage']==False] * self.DfCharges.Tantiemes.loc[self.DfCharges['TopConsommationDeChauffage']==False] ) / self.CaracteristiquesDeLaResidence.TantiemesTotaux
        else:
            self.DfCharges.loc[:,'Charges pour les lots sélectionnés'] = (self.DfCharges.Charge * self.DfCharges.Tantiemes) / self.CaracteristiquesDeLaResidence.TantiemesTotaux

    def Etape1bParametrerLesTemperatures(self, TemperatureLot=19, TemperatureExterieure=19, TemperatureResidence=19, NbHeuresDeChauffe=2000):
        """
        Méthode permettant de paramétrer les températures pour le calcul des charges de chauffage.
        La température de la résidence inclue celle des lots sélectionnées, la temperature des lots non sélectionnés n'est pas la température de la résidence 
        """
        #Paramètres de température
        self.TemperatureLot = TemperatureLot
        self.TemperatureExterieure = TemperatureExterieure
        self.TemperatureResidence = TemperatureResidence

        #Paramètres de résidence$
        self.NombreHeuresDeChauffe=NbHeuresDeChauffe

        self.flagPasDeChauffageUtilise=max(TemperatureResidence, TemperatureExterieure,TemperatureLot)==TemperatureExterieure

        #Calcul de la déperdition de chaleur
        self.PuissanceDeChauffeNecessaireEnWatt=self.CaracteristiquesDeLaResidence.VolumeTotalAChaufferM3*self.CaracteristiquesDeLaResidence.CoefficientIsolation*max(0,(self.TemperatureResidence-self.TemperatureExterieure))
        self.PuissanceDeChauffeNecessaireEnKWH=self.NombreHeuresDeChauffe*self.PuissanceDeChauffeNecessaireEnWatt/1000

        #Calcul des charges pour chaque chaudière en fonction de l'ordre d'utilisation
        ###Initialisation de la puissance de chauffe restante à distribuer entre les chaudières
        puissanceDeChauffeRestante=self.PuissanceDeChauffeNecessaireEnKWH
        for chaudiere in self.ChaudieresDeLaResidence:
            #Calcul de la puissance de chauffe utilisée pour cette chaudière
            puissanceDeChauffeUtiliseeEnkWh=min(chaudiere.ProductionMaxkW*self.NombreHeuresDeChauffe, puissanceDeChauffeRestante)
            chaudiere.PuissanceUtiliseeEnkWh=puissanceDeChauffeUtiliseeEnkWh
            #Calcul du coût de la charge pour cette chaudière
            coutDeLaCharge=puissanceDeChauffeUtiliseeEnkWh*chaudiere.PrixkWh

            #Mise à jour dans le tableau des charges
            self.DfCharges.loc[self.DfCharges['ID prestation'] == chaudiere.IDPrestation, 'Charge'] =  (not self.flagPasDeChauffageUtilise) * coutDeLaCharge
            
            #Mise à jour de la puissance de chauffe restante
            puissanceDeChauffeRestante-=puissanceDeChauffeUtiliseeEnkWh

#Import de données de provision, prestations et tantièmes
@st.cache_data
def ImporterDonneesDeLaResidence():
    DonneesDeLaResidence= pd.read_excel("input.xlsx", sheet_name=["Provisions", "Prestations", "Lots","Residence","Chauffage central"])
    #Récupérer un dictionnaire de tantièmes pour les lots
    residence = Residence(
        DonneesDeLaResidence["Residence"].iloc[0]["Label"],
        DonneesDeLaResidence["Residence"].iloc[0]["Tantiemes totaux"], 
        DonneesDeLaResidence["Residence"].iloc[0]["Volume à chauffer en m3"],
        DonneesDeLaResidence["Residence"].iloc[0]["Coefficient d'isolation"],
        )

    LstChaudieres = [Chaudiere(
        row["Type de chaudière"], 
        row["ID poste de provision"],
        row["Prix unitaire du kWh"],
        row["Production maximum en kW"],
        row["Ordre d'utilisation"]
        ) for index, row in DonneesDeLaResidence["Chauffage central"].iterrows() if isinstance(row["Ordre d'utilisation"],(float,int))]    

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
        row["ID tantiemes"]
        ) for index, row in DonneesDeLaResidence["Provisions"].iterrows()]

    LstPrestations = [Prestation(
        row["Label de la prestation"], 
        row["Total TTC"],
        row["Description"],
        row["Prestataire"],
        row["ID prestation"]
    ) for index, row in DonneesDeLaResidence["Prestations"].iterrows()]
    return LstLots, LstProvisions, LstPrestations,residence, LstChaudieres

LstLots, LstProvisions, LstPrestations,LaResidence, LstChaudieres = ImporterDonneesDeLaResidence()
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
SimulationEnCours=CalculateurDeCharges(LstLotsChoisis, LstProvisions,LaResidence,LstChaudieres)
#Choix de simuler la consommation de chauffage à partir de la température
TopTemperature=st.toggle("Paramétrer un scénario de température précis", key=f"toggle_temperature")
if TopTemperature:
    col_temp1, col_temp2, col_temp3, col_nbHeures = st.columns(4)
    with col_temp1:
        temperatureExterieure = st.slider("Température à l'extérieur de la résidence (°C)", -100, 25, 20, key=f"temp_ext")
    with col_temp2:
        temperatureDuLot = st.slider("Température intérieure des lots (°C)", 0, 25, 25, key=f"temp_lot")
    with col_temp3:
        temperatureResidence = st.slider("Température moyenne de la résidence (°C)", 0, 25, 25, key=f"temp_res")
    with col_nbHeures:
        nbHeuresDeChauffe=st.number_input("Saisissez le nombre d'heures de chauffe",0,10000,2000)
    SimulationEnCours.Etape1bParametrerLesTemperatures(
        TemperatureLot=temperatureDuLot,TemperatureExterieure=temperatureExterieure,TemperatureResidence=temperatureResidence,NbHeuresDeChauffe= nbHeuresDeChauffe)
    
    with st.expander("Voir les paramètres de température et de chauffage"):
        with st.container(border=True):
            st.write(f"Puissance de chauffe nécessaire pour la résidence : {SimulationEnCours.PuissanceDeChauffeNecessaireEnWatt:.0f} W soit {SimulationEnCours.PuissanceDeChauffeNecessaireEnKWH:.0f} kWh")
            st.write(f"Paramètres des chaudières :")
            for chaudiere in SimulationEnCours.ChaudieresDeLaResidence:
                st.write(f"**Chaudière : {chaudiere.Nom}**")
                st.write(f"- Production max. {chaudiere.ProductionMaxkW} kW, Prix: {chaudiere.PrixkWh:.4f} €/kWh")
                st.write(f"- Puissance utilisée : {chaudiere.PuissanceUtiliseeEnkWh:.2f} kWh (Taux d'utilisation: {((chaudiere.PuissanceUtiliseeEnkWh/SimulationEnCours.NombreHeuresDeChauffe)/chaudiere.ProductionMaxkW)*100:.0f}%), Coût de la charge : {chaudiere.PuissanceUtiliseeEnkWh*chaudiere.PrixkWh:.2f} €")

#Initialisation des prestations choisies
prestationsChoisies = []

#Afficher les provisions et donner l'option de sélectionner une prestation s'il y a en a une
for index, row in SimulationEnCours.DfCharges[SimulationEnCours.DfCharges['Tantiemes'] > 0].iterrows():
    IDPrestationActuel=row["ID prestation"]
    #Est ce que c'est de la consommation de chauffage
    TopConsommationDeChauffage=row["TopConsommationDeChauffage"]

    with st.container(border=True):
        #Indiquer le poste de provision en gros puis la description en dessous
        st.markdown(f"<h3 style='text-align: center;'> {row['Postes de provisions']} </h3>",unsafe_allow_html=True)
        st.write(f"{row['Description']}")
        
        #Cas pour la consommation de chauffage
        #Si simulation selon températures activées
        if not(TopTemperature & TopConsommationDeChauffage):
            #Valeur définie selon les prestations choisies  
            optionsDePrestations = [prestation for prestation in LstPrestations if prestation.IDPrestation == IDPrestationActuel]
            if optionsDePrestations:
                prestationsSelectionnees = st.multiselect(
                        f"Choisissez un ou plusieurs devis pour ce poste",
                        options=optionsDePrestations,
                        format_func=lambda prestation: f"🔹 {prestation.Nom} - {prestation.Prestataire}",
                        key=f"prestations_{IDPrestationActuel}"
                    )
                #Ajout des prestations à la liste des prestations choisies pour le calcul des charges
                prestationsChoisies.extend(prestationsSelectionnees)
            else:
                prestationsSelectionnees=[]
        
            #Calcul de la charge résultant des prestations choisies pour ce poste de provision
            SimulationEnCours.Etape1aConstruireTableauDeCharges(IDPrestationActuel, prestationsSelectionnees)
        #Intégrer les charge dans le tableau des charges 
        SimulationEnCours.Etape2CalculerLesChargesParLot(TopTemperature)
        
        #Récupérer le cout pour les lots
        coutResidence = SimulationEnCours.DfCharges.loc[SimulationEnCours.DfCharges['ID prestation'] == IDPrestationActuel, 'Charge'].iloc[0]
        coutLots=SimulationEnCours.DfCharges.loc[SimulationEnCours.DfCharges['ID prestation'] == IDPrestationActuel, 'Charges pour les lots sélectionnés'].iloc[0]
        
        #Boucles d'explication des charges
        colPrestation, colSynthese = st.columns(2)
        with colPrestation:
            for prestation in prestationsSelectionnees:
                with st.container(border=True):
                    st.write(f"**{prestation.Nom}**")
                    st.write(f"Prestataire: **_{prestation.Prestataire}_**")
                    st.write(f"Description: {prestation.Description}")
        with colSynthese:
            with st.container(border=True):
                st.write(f"Coût de la provision : {row['Provisions']:.2f} €")
                st.write(f"Coût de la charge pour la résidence : {coutResidence:.2f} €")
                st.write(f"**Détail du calcul**")
                st.write(f"Les lots sélectionnés corresponent au total à {row['Tantiemes']:.0f} tantièmes associés sur {SimulationEnCours.CaracteristiquesDeLaResidence.TantiemesTotaux} tantièmes totaux de la résidence.")
                if not(TopConsommationDeChauffage) or not(TopTemperature):
                    st.latex(f"{coutResidence:.0f}\\times \\frac{{{row['Tantiemes']:.0f}}}{{{SimulationEnCours.CaracteristiquesDeLaResidence.TantiemesTotaux}}} = {coutLots:.2f}\\text{{ €/an}}")
                elif SimulationEnCours.flagPasDeChauffageUtilise:
                    st.write(f"La température extérieure est supérieure à la température dans les lots sélectionnées et dans la résidence, donc il n'y a pas de consommation de chauffage.")
                else:
                    st.latex(f"{coutResidence:.0f} \\times \\frac{{{row['Tantiemes']:.0f}}}{{{SimulationEnCours.CaracteristiquesDeLaResidence.TantiemesTotaux}}} \\times \\left( 30\\% + 70\\% \\times \\frac{{{SimulationEnCours.TemperatureLot}\\text{{°C}} - {SimulationEnCours.TemperatureExterieure}\\text{{°C}}}}{{{SimulationEnCours.TemperatureResidence}\\text{{°C}} - {SimulationEnCours.TemperatureExterieure}\\text{{°C}}}} \\right) = {coutLots:.2f}\\text{{ €/an}}")
                st.write(f"Le coût de la charge pour les lots sélectionnés est donc de {coutLots:.2f} € par an ou {coutLots/12:.2f} € par mois.")

#Afficher tableau des charges                    
st.dataframe(SimulationEnCours.DfCharges.drop(columns=['ID prestation', 'ID tantiemes','Description']))

#Afficher les charges annuelles et mensuelles totales pour les lots sélectionnés
st.write(f"**Total des charges annuelles pour les lots sélectionnés : {SimulationEnCours.DfCharges['Charges pour les lots sélectionnés'].sum():.2f} €**")
st.write(f"**Total des charges mensuelles pour les lots sélectionnés : {SimulationEnCours.DfCharges['Charges pour les lots sélectionnés'].sum()/12:.2f} €**")