import streamlit as st
import pandas as pd

#
# Classe de Calculateur de charges de copropriété
#

class Lot:
    """
    Classe d'objet permettant de définir un lot de copropriété avec ses ID et ses tantièles associés aux subdivisions.
    """
    def __init__(self, IDCommercial, IDNotaire, DicoTaxonomieTantiemes: dict[str,str]):
        self.IDNotaire = IDNotaire

        #Créer un dico pour initialiser le tableau des tantièmes
        tableauTantiemesInitialise = {
            'Label des subdivisions': DicoTaxonomieTantiemes.value(),
            'ID des subdivisions': DicoTaxonomieTantiemes.keys(),
            'Tantiemes':0
        }
        self.DfTantiemes= pd.DataFrame(tableauTantiemesInitialise)

    def DefinirTantiemes(self, TantiemesParSubdivision: dict[str, int]):
        for IDSubdivision, tantiemes in TantiemesParSubdivision.items():
            self.DfTantiemes.loc[self.DfTantiemes['ID des subdivisions'] == IDSubdivision, 'Tantiemes'] = tantiemes

class Prestation:
    """
    Classe d'objet permettant de définir une prestation de copropriété avec son nom et son coût associé.
    """
    def __init__(self, Nom, Cout,Description,ID=None):
        self.Nom = Nom
        self.Cout = Cout
        self.Description = Description
        self.ID = ID

class Provision:
    """
    Classe d'objet permettant de définir une provision de copropriété avec son nom et son montant associé.
    """
    def __init__(self, Nom, Provision,Description,TopConsommationChauffage=False,ID=None):
        self.Nom = Nom
        self.Provision = Provision
        self.Description = Description
        self.ID = ID
        self.TopConsommationChauffage=TopConsommationChauffage 

class CalculateurDeCharges:
    """
    Classe d'objet permettant de calculer les charges de copropriété en fonction des lots, des prestations et des provisions.
    """
    def __init__(self,LstLot:  List[Lot],
                LstProvisions: List[Provision], 
                TantiemesTotaux=10000):
        self.Lots = LstLot
        self.TantiemesTotaux = TantiemesTotaux

        #Créer un dico pour initialiser le tableau des tantièmes
        tableauTantiemesInitialise = {
            'Postes de provisions': [provision.Nom for provision in LstProvisions],
            'Tantiemes': 0,
            'Provisions':[provision.Provision for provision in LstProvisions],
        }
        self.DfCharges= pd.DataFrame(tableauTantiemesInitialise)

        #Incrémenter les tantièmes dans le tableau des charges
        for provision in LstProvisions:
            for lot in LstLot:
                #On récupère les tantièmes du lot pour le poste de provision
                tantiemesLot = lot.DfTantiemes.loc[lot.DfTantiemes['ID des subdivisions'] == provision.ID, 'Tantiemes'].values[0]
                #On l'ajoute dans le tableau des charges
                self.DfCharges.loc[self.DfCharges['Postes de provisions'] == provision.Nom, 'Tantiemes'] += tantiemesLot

    def Etape1ConstruireTableauDeCharges (self, LstPrestationsSelectionnees: List[Prestation]):
        """
        Méthode permettant de calculer les charges totales de copropriété en fonction des prestations et des provisions.
        """
        #Sauvegarder la liste de prestations sélectionnées
        self.PrestationsSelectionnees = LstPrestationsSelectionnees
        #Réinitialiser les charges à 0
        self.DfCharges['Charge'] = 0

        #Itération pour calculer les charges totales
        for provision in self.DfCharges.itertuples():
            CoutReelDuPosteDeProvision = 0
            #Pour chaque provision on checke si on a des prestations associées
            for prestation in self.PrestationsSelectionnees:
                #S'il y a des prestations associées à la provision, on ajoute le coût de la prestation aux charges totales
                if prestation.IDPosteDeProvision == provision.IDPosteDeProvision:
                    CoutReelDuPosteDeProvision += prestation.Cout
            #Si aucune prestation n'est associée à la provision, on prend le coût de la provision
            if CoutReelDuPosteDeProvision==0:
                CoutReelDuPosteDeProvision=provision.Cout
            #On ajoute le coût réel du poste de provision aux charges totales
            self.DfCharges.loc[self.DfCharges['Postes de provisions'] == provision.Nom, 'Charge'] = CoutReelDuPosteDeProvision

    def Etape2CalculerLesChargesParLot (self):
        """
        Méthode permettant de calculer les charges par lot en fonction des tantièmes et des charges totales.
        """
        #Pour chaque tantièmes on calcul les couts
        self.DfCharges['Charges pour les lots sélectionnés'] = self.DfCharges.Charge * self.DfCharges.Tantiemes / self.TantiemesTotaux

    def Etape3InclureLaConsommationIndividuelleDeChauffage (self, 
                TemperatureLot=19, TemperatureExterieure=19, TemperatureResidence=19, 
                PrixTonneDeGranule=500,#392 pour CRAM, 392 pour PROCHALOR 
                PrixMWhGaz=100, 
                ConsommationTonnesGranule=40, ConsommationMWhGaz=30):
        """
        Méthode permettant d'inclure la consommation individuelle de chauffage dans le calcul des charges par lot.
        """
        self.TemperatureLot = TemperatureLot
        self.TemperatureExterieure = TemperatureExterieure
        self.TemperatureResidence = TemperatureResidence

        self.PrixTonneDeGranule = PrixTonneDeGranule
        self.PrixMWh = PrixMWhGaz

        self.ConsommationTonnesGranule = ConsommationTonnesGranule
        self.ConsommationMWhGaz = ConsommationMWhGaz
        #On fait le calcul de la consommation individuelle de chauffage en fonction des températures et des prix
        self.ChargeTotaleDeGranuleDeLaResidence=self.ConsommationTonnesGranule * self.PrixTonneDeGranule
        self.ChargeTotaleDeGazDeLaResidence=self.ConsommationMWhGaz * self.PrixMWh

        self.ChargeCommuneDeGranule=self.ChargeTotaleDeGranuleDeLaResidence * 0.3
        self.ChargeCommuneDeGaz=self.ChargeTotaleDeGazDeLaResidence * 0.3

        self.ChargeIndividuelleDeGranule=self.ChargeTotaleDeGranuleDeLaResidence * 0.7 * (self.TemperatureLot - self.TemperatureExterieure) / (self.TemperatureResidence - self.TemperatureExterieure)
        self.ChargeIndividuelleDeGaz=self.ChargeTotaleDeGazDeLaResidence *0.7 * (self.TemperatureLot - self.TemperatureExterieure) / (self.TemperatureResidence - self.TemperatureExterieure)

        self.DfCharges.loc[self.DfCharges['Postes de provisions'] == "Consommation de chauffage", 'Charge'] = self.ChargeIndividuelleDeGranule + self.ChargeIndividuelleDeGaz
#
# Début de l'affiche du site web #
# 

# Titre de l'application
st.title("Calculateur de charges de copropriété")

# Un sous-titre
st.subheader("Ce calculateur permet d'estimer les charges de copropriété en fonction des prestations sélectionnées et des tantièmes des lots choisis")

# Un widget interactif : une boîte de saisie de texte
nom = st.text_input("Quel est votre nom ?")

# Une condition pour afficher un message si le texte est rempli
if nom:
    st.write(f"Bonjour {nom} ! Ravi de vous rencontrer.")

# Un slider interactif
age = st.slider("Sélectionnez votre âge", 0, 100, 25)
st.write(f"Vous avez {age} ans.")